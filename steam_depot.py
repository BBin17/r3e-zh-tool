"""Read an installed Steam app's file fingerprint from its local depot cache."""
from __future__ import annotations

import hashlib
import re
import struct
from dataclasses import dataclass
from pathlib import Path, PureWindowsPath

_APP_LIMIT = 1 << 20
_DEPOT_LIMIT = 64 << 20
_VDF_TOKEN = re.compile(r'\s+|//[^\r\n]*|[{}]|"(?:\\[^\r\n]|[^"\\\r\n])*"')
_ID = re.compile(r'[1-9][0-9]{0,19}')
_SECTIONS = (0x71F617D0, 0x1F4812BE, 0x1B81B817)  # Payload, metadata, signature
_END_MAGIC = 0x32C415AB


@dataclass(frozen=True)
class InstalledFile:
    app_manifest_hash: bytes
    size: int
    sha1: bytes

    def matches(self, contents: bytes) -> bool:
        return len(contents) == self.size and hashlib.sha1(contents).digest() == self.sha1


def _read_bounded(path: Path, limit: int) -> bytes:
    with path.open('rb') as stream:
        data = stream.read(limit + 1)
    if len(data) > limit:
        raise ValueError('Steam manifest exceeds size limit')
    return data


def _read_app_state(data: bytes) -> dict:
    text = data.decode('utf-8-sig')
    stack: list[dict] = [{}]
    key = None
    offset = 0
    while offset < len(text):
        match = _VDF_TOKEN.match(text, offset)
        if match is None:
            raise ValueError('Invalid Steam app manifest token')
        offset = match.end()
        token = match[0]
        if token.isspace() or token.startswith('//'):
            continue
        if token == '{' and key is not None and len(stack) < 16:
            child: dict = {}
            stack[-1][key] = child
            stack.append(child)
            key = None
        elif token == '}' and key is None and len(stack) > 1:
            stack.pop()
        elif token.startswith('"'):
            value = re.sub(r'\\(["\\])', r'\1', token[1:-1])
            if key is None:
                key = value.casefold()
                if key in stack[-1]:
                    raise ValueError('Duplicate Steam app manifest key')
            else:
                stack[-1][key] = value
                key = None
        else:
            raise ValueError('Invalid Steam app manifest structure')
    state = stack[0].get('appstate')
    if len(stack) != 1 or key is not None or not isinstance(state, dict):
        raise ValueError('Incomplete Steam app manifest')
    return state


def _varint(data: memoryview, offset: int) -> tuple[int, int]:
    value = 0
    for shift in range(0, 64, 7):
        if offset >= len(data):
            break
        byte = data[offset]
        offset += 1
        if shift == 63 and byte > 1:
            break
        value |= (byte & 127) << shift
        if byte < 128:
            return value, offset
    raise ValueError('Invalid Steam depot manifest varint')


def _fields(data: memoryview):
    offset = 0
    while offset < len(data):
        tag, offset = _varint(data, offset)
        number, wire = tag >> 3, tag & 7
        if not 0 < number < (1 << 29):
            raise ValueError('Invalid Steam depot manifest field')
        if wire == 0:
            value, offset = _varint(data, offset)
        else:
            if wire == 2:
                size, offset = _varint(data, offset)
            elif wire in (1, 5):
                size = 8 if wire == 1 else 4
            else:
                raise ValueError('Unsupported Steam depot manifest field')
            end = offset + size
            if end > len(data):
                raise ValueError('Truncated Steam depot manifest field')
            value = data[offset:end]
            offset = end
        yield number, wire, value


def _selected_fields(data: memoryview, schema: dict[int, int]) -> dict:
    selected = {}
    for number, wire, value in _fields(data):
        if number in schema:
            if wire != schema[number] or number in selected:
                raise ValueError('Invalid or duplicate Steam depot manifest field')
            selected[number] = value
    return selected


def _depot_file(data: bytes, depot_id: int, manifest_id: int, filename: str) -> tuple[int, bytes] | None:
    sections = []
    offset = 0
    for expected_magic in _SECTIONS:
        magic, size = struct.unpack_from('<II', data, offset)
        offset += 8
        end = offset + size
        if magic != expected_magic or end > len(data):
            raise ValueError('Invalid Steam depot manifest section')
        sections.append(memoryview(data)[offset:end])
        offset = end
    if offset + 4 != len(data) or struct.unpack_from('<I', data, offset)[0] != _END_MAGIC:
        raise ValueError('Incomplete Steam depot manifest')
    payload, metadata, _ = sections
    meta = _selected_fields(metadata, {1: 0, 2: 0, 4: 0})
    if meta.get(1) != depot_id or meta.get(2) != manifest_id or meta.get(4, 0) != 0:
        raise ValueError('Incorrect depot identity or encrypted filenames')

    matched = None
    for number, wire, record in _fields(payload):
        if number != 1:
            continue
        if wire != 2:
            raise ValueError('Invalid Steam depot file mapping')
        fields = _selected_fields(record, {1: 2, 2: 0, 3: 0, 5: 2, 7: 2})
        name = bytes(fields[1]).rstrip(b'\0').decode('utf-8')
        if PureWindowsPath(name).as_posix().lower() != filename:
            continue
        size = fields.get(2, 0)
        digest = bytes(fields.get(5, b''))
        # Valve flags 64 and 512 mark a directory and a symlink respectively.
        if matched is not None or not size or len(digest) != 20 or fields.get(3, 0) & (64 | 512) or fields.get(7):
            raise ValueError('Ambiguous or invalid Steam depot file')
        matched = size, digest
    return matched


def installed_file(game_dir: Path, app_id: str, build: str, relative_path: Path,
                   steam_roots: list[Path]) -> InstalledFile | None:
    """Fail closed if the cache cannot describe the selected, fully installed app."""
    try:
        game_dir = game_dir.resolve()
        steamapps = game_dir.parent.parent
        if game_dir.parent.name.lower() != 'common' or steamapps.name.lower() != 'steamapps':
            return None
        app_data = _read_bounded(steamapps / f'appmanifest_{app_id}.acf', _APP_LIMIT)
        state = _read_app_state(app_data)
        if (state.get('appid') != app_id or state.get('buildid') != build or
                state.get('stateflags') != '4' or not isinstance(state.get('installdir'), str) or
                state['installdir'].lower() != game_dir.name.lower()):
            return None
        depots = state.get('installeddepots')
        if not isinstance(depots, dict) or not 0 < len(depots) <= 32:
            return None
        cache_dirs = [steamapps.parent / 'depotcache', steamapps / 'depotcache']
        for root in steam_roots:
            cache_dirs.extend((root / 'depotcache', root / 'steamapps' / 'depotcache'))
        cache_dirs = list(dict.fromkeys(cache_dirs))
        matched = None
        for depot, row in depots.items():
            manifest = row.get('manifest') if isinstance(row, dict) else None
            if not _ID.fullmatch(depot) or not isinstance(manifest, str) or not _ID.fullmatch(manifest):
                return None
            name = f'{depot}_{manifest}.manifest'
            for folder in cache_dirs:
                try:
                    data = _read_bounded(folder / name, _DEPOT_LIMIT)
                except FileNotFoundError:
                    continue
                break
            else:
                return None
            result = _depot_file(data, int(depot), int(manifest), relative_path.as_posix().lower())
            if result is not None:
                if matched is not None:
                    return None
                matched = result
        if matched is not None:
            return InstalledFile(hashlib.sha256(app_data).digest(), *matched)
    except (OSError, ValueError, KeyError, RuntimeError, struct.error):
        return None
    return None
