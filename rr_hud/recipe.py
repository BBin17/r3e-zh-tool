"""Generate translated race HUD files from a local RaceRoom installation."""
from __future__ import annotations

from collections.abc import Iterable, Mapping
import ctypes
from ctypes import wintypes
import hashlib
from io import BytesIO
import json
import os
from pathlib import Path
import re

from ._translations import MFD_OPTIONS, NATIVE_LABELS, PANELS


SYSTEM_FONT = Path(os.environ.get('SystemRoot', r'C:\Windows')) / 'Fonts' / 'msyhbd.ttc'
FONT_NAME = 'r3eracezh'
RECEIPT = 'receipt.json'
LEGACY_PANELS = frozenset({'timing_panel', 'pit_limiter', 'status_strip'})
# These short messages are supplied by the game at runtime, not by the HUD manifest.
_MESSAGE_TEXT = (
    '行车线 辅助线 开启关闭 理想 自己或挑战对象'
    '手动变速箱 自动变速箱 幽灵车 历史最佳 本场最快'
    '刹车偏置 牵引力控制 制动能量回收 发动机映射 FFB 倍率'
    '反打方向辅助 车身稳定控制 原厂 ABS TC MGU预设 放电速率 剩余水量'
    '所挑战的幽灵车下载失败 你的排行榜成绩上传失败 竞赛连接错误 更改语言失败！'
    '：、％（）'
)

_MFD_SIGNALS = {
    'vehValue7': 'vehHeadlightsText',
    'pitValue0': 'pitPresetText',
    'pitValue1': 'pitPenaltyText',
    'pitValue2': 'pitDriverChangeText',
    'pitValue4': 'pitFrontTyreText',
    'pitValue5': 'pitRearTyreText',
    'pitValue6': 'pitBodyText',
    'pitValue7': 'pitFrontAeroText',
    'pitValue8': 'pitRearAeroText',
    'pitValue9': 'pitSuspensionText',
}

# Inspect only bounded local byte streams. Matching full ASCII words keeps known
# state tokens separate from longer identifiers and resource paths.
_NATIVE_SOURCE_LIMIT = 64 * 1024 * 1024
_ASCII_WORD = re.compile(rb'[A-Za-z]+')


def digest(path: Path) -> str:
    with path.open('rb') as src:
        return hashlib.file_digest(src, 'sha256').hexdigest()


def native_labels(sources: Iterable[Path]) -> dict[str, str]:
    """Read candidate words from the game files without loading executable code."""
    missing = {word for _, words in NATIVE_LABELS.values() for word in words}
    words_found = {}
    checked = set()
    for source in sources:
        try:
            with source.open('rb') as stream:
                if os.fstat(stream.fileno()).st_size > _NATIVE_SOURCE_LIMIT:
                    continue
                data = stream.read(_NATIVE_SOURCE_LIMIT + 1)
        except OSError:
            continue
        if len(data) > _NATIVE_SOURCE_LIMIT:
            continue
        for match in _ASCII_WORD.finditer(data):
            if match.end() - match.start() > 16:
                continue
            word = match.group().upper()
            if word in checked:
                continue
            checked.add(word)
            checksum = hashlib.sha256(word).hexdigest()
            if checksum in missing:
                words_found[checksum] = word
                missing.remove(checksum)
                if not missing:
                    break
        if not missing:
            break

    result = {}
    for target, (checksum, words) in NATIVE_LABELS.items():
        if all(word in words_found for word in words):
            source = b' '.join(words_found[word] for word in words)
            if hashlib.sha256(source).hexdigest() == checksum:
                result[target] = source.decode('ascii')
    return result


def _translated_value(value, translations, seen):
    if isinstance(value, str):
        checksum = hashlib.sha256(value.encode('utf-8')).hexdigest()
        if checksum in translations:
            seen.add(checksum)
            return translations[checksum]
    if isinstance(value, list):
        return [_translated_value(item, translations, seen) for item in value]
    if isinstance(value, dict) and 'args' in value:
        return {**value, 'args': _translated_value(value['args'], translations, seen)}
    return value


def _native_expression(element_id, value, labels):
    if element_id in _MFD_SIGNALS:
        valid = value == {'signal': _MFD_SIGNALS[element_id]}
    elif element_id == 'pitButtonText':
        valid = value == {'op': 'uppercase', 'args': [{'signal': 'pitButtonText'}]}
    else:
        valid = isinstance(value, dict) and value.get('op') == 'if'
    if not valid:
        raise ValueError(f'mfd 的 {element_id} 状态表达式已变化。')

    # Comparison is case-insensitive as in v2. The original expression is the
    # final fallback for custom presets, other languages and unknown values.
    comparison = {'op': 'uppercase', 'args': [value]}
    result = value
    for target in reversed(MFD_OPTIONS[element_id]):
        if target in labels:
            match = {'op': 'eq', 'args': [comparison, labels[target]]}
            result = {'op': 'if', 'args': [match, target, result]}
    return result


def translate_panel(name: str, original: bytes, labels: Mapping[str, str] | None = None) -> dict:
    panel = json.loads(original.decode('utf-8-sig'))
    if (not isinstance(panel, dict) or not isinstance(panel.get('fonts'), dict)
            or not isinstance(panel.get('elements'), list)):
        raise ValueError(f'{name} 的 HUD 原版文件格式不兼容。')
    if FONT_NAME in panel['fonts']:
        raise ValueError(f'{name} 已包含汉化字体，请先恢复原件。')
    expected = PANELS[name]
    options = MFD_OPTIONS.keys() if name == 'mfd' else set()
    element_ids = expected.keys() | options
    found = set()
    for element in panel['elements']:
        if not isinstance(element, dict) or not isinstance(element.get('id'), str):
            raise ValueError(f'{name} 的 HUD 原版组件格式不兼容。')
        element_id = element['id']
        if element_id not in element_ids:
            continue
        if element_id in found or element.get('type') != 'text' or 'value' not in element:
            raise ValueError(f'{name} 的 {element_id} 已变化。')
        if name == 'message_log' and element['value'] != {'signal': f'{element_id[:-4]}_text'}:
            raise ValueError(f'{name} 的 {element_id} 消息信号已变化。')
        translations = expected.get(element_id, {})
        seen = set()
        value = _translated_value(element['value'], translations, seen) if translations else element['value']
        if seen != translations.keys():
            raise ValueError(f'{name} 的 {element_id} 文案已变化，需要重新适配。')
        if element_id in options:
            value = _native_expression(element_id, value, labels or {})
        element['value'] = value
        element['fontFamily'] = FONT_NAME
        element.pop('fontWeight', None)
        found.add(element_id)
    if found != element_ids:
        raise ValueError(f'{name} 缺少原版组件，需要重新适配。')
    panel['fonts'][FONT_NAME] = {}
    return panel


class _ProcessEntry(ctypes.Structure):
    _fields_ = [
        ('dwSize', wintypes.DWORD), ('cntUsage', wintypes.DWORD),
        ('th32ProcessID', wintypes.DWORD), ('th32DefaultHeapID', ctypes.c_size_t),
        ('th32ModuleID', wintypes.DWORD), ('cntThreads', wintypes.DWORD),
        ('th32ParentProcessID', wintypes.DWORD), ('pcPriClassBase', wintypes.LONG),
        ('dwFlags', wintypes.DWORD), ('szExeFile', wintypes.WCHAR * 260),
    ]


def game_running() -> bool:
    """Use the Windows process snapshot API, including processes in other sessions."""
    if os.name != 'nt':
        raise RuntimeError('HUD 文件操作仅支持 Windows。')
    kernel = ctypes.WinDLL('kernel32', use_last_error=True)
    snapshot = kernel.CreateToolhelp32Snapshot
    snapshot.argtypes = [wintypes.DWORD, wintypes.DWORD]
    snapshot.restype = wintypes.HANDLE
    close = kernel.CloseHandle
    close.argtypes = [wintypes.HANDLE]
    first = kernel.Process32FirstW
    following = kernel.Process32NextW
    for step in (first, following):
        step.argtypes = [wintypes.HANDLE, ctypes.POINTER(_ProcessEntry)]
        step.restype = wintypes.BOOL

    handle = snapshot(0x2, 0)  # TH32CS_SNAPPROCESS
    if handle == ctypes.c_void_p(-1).value:
        raise RuntimeError('无法确认 RaceRoom 是否已退出，请重试。') from ctypes.WinError(ctypes.get_last_error())
    try:
        entry = _ProcessEntry(dwSize=ctypes.sizeof(_ProcessEntry))
        if not first(handle, ctypes.byref(entry)):
            raise RuntimeError('无法读取 Windows 进程列表，请重试。') from ctypes.WinError(ctypes.get_last_error())
        while True:
            if entry.szExeFile.casefold() in {'rrre64.exe', 'rrre.exe'}:
                return True
            if not following(handle, ctypes.byref(entry)):
                error = ctypes.get_last_error()
                if error == 18:  # ERROR_NO_MORE_FILES
                    return False
                raise RuntimeError('无法读取 Windows 进程列表，请重试。') from ctypes.WinError(error)
    finally:
        close(handle)


def _font_sources() -> tuple[Path, ...]:
    return (SYSTEM_FONT, *(SYSTEM_FONT.with_name(name)
                           for name in ('msyh.ttc', 'Deng.ttf', 'simhei.ttf', 'simsun.ttc')))


def _alphabet() -> str:
    return ''.join(map(chr, range(32, 127))) + ''.join(
        target for elements in PANELS.values() for labels in elements.values() for target in labels.values()
    ) + ''.join(NATIVE_LABELS) + _MESSAGE_TEXT


def _subset_font(source, alphabet, panels):
    from fontTools.subset import Options, Subsetter
    from fontTools.ttLib import TTFont

    output = BytesIO()
    with TTFont(source, fontNumber=0) as font:
        if 'glyf' not in font or 'OS/2' not in font or font['OS/2'].fsType & 0x0302:
            raise ValueError('此字体不支持所需的 TrueType 字形或字体子集。')
        cmap = font.getBestCmap() or {}
        missing = sorted(set(map(ord, alphabet)) - cmap.keys())
        if missing:
            raise ValueError('字体缺少字符：' + ''.join(map(chr, missing)))
        # Keep common non-Chinese characters used by the message log.
        additional = {code for code in cmap
                      if 0xA0 <= code <= 0x52F or 0x1E00 <= code <= 0x20CF}
        options = Options()
        options.hinting = False
        subset = Subsetter(options=options)
        subset.populate(text=alphabet, unicodes=additional)
        subset.subset(font)
        font.save(output)

    output.seek(0)
    with TTFont(output) as font:
        cmap = font.getBestCmap() or {}
        if set(map(ord, alphabet)) - cmap.keys():
            raise ValueError('HUD 字体子集校验失败。')
        for name, panel in panels.items():
            for element in panel['elements']:
                value, width = element.get('value'), element.get('width')
                if (element.get('fontFamily') != FONT_NAME or not isinstance(value, str)
                        or not isinstance(width, (int, float))):
                    continue
                size = element.get('fontSize')
                if not isinstance(size, (int, float)) or size <= 0:
                    raise ValueError(f'{name} 的 {element["id"]} HUD 字号无效。')
                advance = sum(font['hmtx'][cmap[ord(char)]][0] for char in value)
                if advance * size / font['head'].unitsPerEm > width:
                    raise ValueError(f'{name} 的 {element["id"]} 中文超出原有宽度。')
    return output.getvalue()


def _select_font(sources, panels):
    try:
        from fontTools.ttLib import TTLibError
    except ImportError as exc:
        raise RuntimeError('缺少 HUD 字体组件 fontTools。') from exc

    alphabet = _alphabet()
    failure = None
    for source in sources:
        try:
            return _subset_font(source, alphabet, panels)
        except (OSError, KeyError, TTLibError, ValueError) as exc:
            failure = f'{source.name}：{exc}'
    raise ValueError(f'没有可用于 HUD 的 Windows 简体中文字体。{failure or ""}')


def probe_font() -> bool:
    """Check the bundled font tooling against an installed font when present."""
    import fontTools.subset  # Validate build imports even without a system font.

    sources = tuple(source for source in _font_sources() if source.is_file())
    if not sources:
        return False
    _select_font(sources, {})
    return True


def font_available() -> bool:
    return any(source.is_file() for source in _font_sources())


def prepare(stage: Path, originals: Mapping[str, Path], *, labels: Mapping[str, str]) -> dict:
    """Write and validate the proposed HUD assets in a transaction directory."""
    panels, paths = {}, {}
    for name in PANELS:
        original = originals[name].read_bytes()
        panel = panels[name] = translate_panel(name, original, labels)
        output = stage / f'{name}.json'
        output.write_text(json.dumps(panel, ensure_ascii=False, separators=(',', ':')), encoding='utf-8')
        paths[name] = {'original': hashlib.sha256(original).hexdigest(), 'localized': digest(output)}
    sources = tuple(source for source in _font_sources() if source.is_file())
    (stage / f'{FONT_NAME}.ttf').write_bytes(_select_font(sources, panels))
    return paths
