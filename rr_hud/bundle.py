"""Transactional installer for the RaceRoom HUD translation."""
from __future__ import annotations

from contextlib import contextmanager
import ctypes
from ctypes import wintypes
import hashlib
import json
import os
from pathlib import Path
import re
from stat import FILE_ATTRIBUTE_REPARSE_POINT
from tempfile import mkstemp, TemporaryDirectory

from . import recipe


BACKUP_DIR = 'zh-hud-backups'
CUSTOM_FONT = f'{recipe.FONT_NAME}.ttf'
HUD_VERSION = 3
_RECEIPT_PANELS = {
    1: recipe.LEGACY_PANELS,
    2: recipe.PANELS.keys() - {'message_log'},
    HUD_VERSION: recipe.PANELS.keys(),
}
CLOSE_GAME = '请先退出 RaceRoom，再操作 HUD 汉化。'


def _direct(path: Path) -> Path:
    # Work within the selected game directory, even if an inner path is redirected.
    if path.resolve() != path:
        raise ValueError(f'HUD 路径存在重定向，操作已停止：{path}')
    for part in (path, *path.parents):
        try:
            attributes = part.lstat().st_file_attributes
        except FileNotFoundError:
            continue
        if attributes & FILE_ATTRIBUTE_REPARSE_POINT:
            raise ValueError(f'HUD 路径存在重定向，操作已停止：{part}')
    return path


def _layout(game_dir: Path) -> tuple[Path, Path]:
    if os.name != 'nt':
        raise RuntimeError('HUD 文件操作仅支持 Windows。')
    root = game_dir.resolve(strict=True)
    data = root / 'Game' / 'GameData'
    hud = _direct(data / 'Cosmo' / 'hud')
    general = _direct(data / 'General')
    if not hud.is_dir() or not general.is_dir():
        raise ValueError('未找到此游戏目录的 RaceRoom HUD 或 General 文件夹。')
    return hud, _direct(general / BACKUP_DIR)


@contextmanager
def _locked(backups: Path):
    # A process exit releases this lock. No lock file is left in the game folder.
    name = hashlib.sha256(str(backups).casefold().encode('utf-8')).hexdigest()
    kernel32 = ctypes.WinDLL('kernel32', use_last_error=True)
    create = kernel32.CreateMutexW
    create.argtypes = [wintypes.LPVOID, wintypes.BOOL, wintypes.LPCWSTR]
    create.restype = wintypes.HANDLE
    close = kernel32.CloseHandle
    close.argtypes = [wintypes.HANDLE]
    release = kernel32.ReleaseMutex
    release.argtypes = [wintypes.HANDLE]

    ctypes.set_last_error(0)
    handle = create(None, True, f'Local\\RaceRoomZhHud-{name}')
    error = ctypes.get_last_error()
    if not handle:
        raise ctypes.WinError(error)
    try:
        if error == 183:  # ERROR_ALREADY_EXISTS
            raise RuntimeError('正在进行另一项 HUD 操作，请稍后重试。')
        try:
            yield
        finally:
            release(handle)
    finally:
        close(handle)


def _require_closed():
    if recipe.game_running():
        raise RuntimeError(CLOSE_GAME)


def _manifest(hud, name):
    return _direct(hud / name / 'manifest.json')


def _font(hud, name):
    return _direct(hud / name / 'fonts' / CUSTOM_FONT)


def _hash(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _file_hash(path: Path) -> str | None:
    try:
        return recipe.digest(path)
    except FileNotFoundError:
        return None


def _valid_hash(value) -> bool:
    return isinstance(value, str) and re.fullmatch('[0-9a-f]{64}', value) is not None


def _receipt(hud, backups):
    raw = _direct(backups / recipe.RECEIPT).read_bytes()
    try:
        receipt = json.loads(raw)
    except (UnicodeError, ValueError) as exc:
        raise ValueError('HUD 备份记录无法读取。') from exc
    if not isinstance(receipt, dict) or not isinstance(receipt.get('hud'), str):
        raise ValueError('HUD 备份记录格式无效。')
    if Path(receipt['hud']) != hud:
        raise ValueError('HUD 备份记录与所选游戏目录不匹配。')
    version = receipt.get('hud_version', 1)
    if type(version) is not int or version not in _RECEIPT_PANELS:
        raise ValueError('此 HUD 备份需要兼容的汉化工具版本。')
    panels = receipt.get('panels')
    if (not isinstance(panels, dict) or panels.keys() != _RECEIPT_PANELS[version]
            or not _valid_hash(receipt.get('font'))
            or any(not isinstance(hashes, dict) or not _valid_hash(hashes.get('original'))
                   or not _valid_hash(hashes.get('localized')) or hashes['original'] == hashes['localized']
                   for hashes in panels.values())):
        raise ValueError('HUD 备份记录的面板或校验值无效。')
    if {entry.name for entry in _direct(backups).iterdir()} != {
        recipe.RECEIPT, *(f'{name}.json' for name in panels)
    }:
        raise ValueError('HUD 备份文件夹包含未知文件或缺少原件。')
    return receipt


def _verify(hud, backups, receipt):
    complete = True
    for name, hashes in receipt['panels'].items():
        if _file_hash(_direct(backups / f'{name}.json')) != hashes['original']:
            raise ValueError(f'{name} 的 HUD 原版备份校验失败。')
        manifest_hash = _file_hash(_manifest(hud, name))
        if manifest_hash not in (hashes['original'], hashes['localized']):
            raise ValueError(f'{name} 的 HUD 文件与备份记录不匹配，可能已被游戏或其他工具修改。')
        font_hash = _file_hash(_font(hud, name))
        if font_hash not in (None, receipt['font']):
            raise ValueError(f'{name} 的 HUD 汉化字体校验失败。')
        complete &= manifest_hash == hashes['localized'] and font_hash == receipt['font']
    return complete


def _check_unbacked(hud, names):
    for name in names:
        if _font(hud, name).exists():
            raise ValueError('检测到没有本地备份的 HUD 汉化，请先用原先的汉化工具恢复 HUD。')
        source = _manifest(hud, name).read_bytes()
        try:
            panel = recipe.translate_panel(name, source)
            if name == 'mfd' and ('r3ecjktest' in panel['fonts']
                                  or _direct(hud / name / 'fonts' / 'r3ecjktest.ttf').exists()):
                raise ValueError('检测到旧版进站菜单实验，请先用原实验工具恢复。')
        except (AttributeError, KeyError, TypeError, UnicodeError) as exc:
            raise ValueError(f'{name} 的 HUD 原版文件格式不兼容。') from exc


def status(game_dir: Path) -> tuple[str, bool, bool]:
    """Report HUD state and the operations currently available to the installer."""
    try:
        hud, backups = _layout(game_dir)
        with _locked(backups):
            _require_closed()
            if backups.exists():
                receipt = _receipt(hud, backups)
                if _verify(hud, backups, receipt):
                    return 'HUD 汉化已安装，可恢复原版。', False, True
                return 'HUD 操作尚未完成，可恢复原版。', False, True
            _check_unbacked(hud, recipe.PANELS)
            if not recipe.font_available():
                return '缺少可用于 HUD 的 Windows 简体中文字体。', False, False
            return 'HUD 尚未安装汉化，可安装。', True, False
    except (OSError, RuntimeError, ValueError) as exc:
        return f'HUD 不可操作：{exc}', False, False


def _replace(data: bytes, target: Path, expected: str | None):
    """Publish a flushed file beside its destination after checking the live hash."""
    _direct(target).parent.mkdir(parents=True, exist_ok=True)
    fd, temp_name = mkstemp(prefix='.r3e-hud-', dir=_direct(target.parent))
    temp = Path(temp_name)
    try:
        with os.fdopen(fd, 'wb') as out:
            out.write(data)
            out.flush()
            os.fsync(out.fileno())
        if _file_hash(_direct(target)) != expected:
            raise ValueError(f'{target.parent.name} 的 HUD 文件在操作期间发生变化：{target.name}')
        if expected is None:
            temp.rename(target)  # Windows rename fails if another file appeared.
        else:
            temp.replace(target)
    finally:
        temp.unlink(missing_ok=True)


def _copy_verified(source: Path, target: Path, source_hash: str, target_hash: str | None = None):
    data = _direct(source).read_bytes()
    if _hash(data) != source_hash:
        raise ValueError(f'HUD 文件校验失败：{source.name}')
    _replace(data, target, target_hash)


def _publish(hud, backups, staged, receipt):
    raw = json.dumps(receipt, ensure_ascii=False, indent=2).encode('utf-8')
    _replace(raw, staged / recipe.RECEIPT, None)
    _verify(hud, staged, receipt)
    _require_closed()
    _direct(staged).rename(_direct(backups))


def _restore(hud, backups):
    _require_closed()
    receipt = _receipt(hud, backups)
    _verify(hud, backups, receipt)
    for name, hashes in receipt['panels'].items():
        _require_closed()
        target = _manifest(hud, name)
        if _file_hash(target) != hashes['original']:
            _copy_verified(backups / f'{name}.json', target, hashes['original'], hashes['localized'])
    # Restore manifests first. A process exit leaves all remaining assets recoverable.
    for name, hashes in receipt['panels'].items():
        _require_closed()
        font = _font(hud, name)
        font_hash = _file_hash(font)
        if _file_hash(_manifest(hud, name)) != hashes['original'] or font_hash not in (None, receipt['font']):
            raise ValueError(f'{name} 的 HUD 文件在恢复期间发生变化。')
        if font_hash is not None:
            font.unlink()

    with TemporaryDirectory(prefix='.r3e-hud-restored-', dir=_direct(backups.parent)) as temp:
        # Retire the entire receipt and originals atomically, once restoration is verified.
        _receipt(hud, backups)
        for name, hashes in receipt['panels'].items():
            if _file_hash(_manifest(hud, name)) != hashes['original'] or _file_hash(_font(hud, name)) is not None:
                raise ValueError(f'{name} 的 HUD 恢复后校验失败。')
        _require_closed()
        _direct(backups).rename(_direct(Path(temp) / 'backup'))


def _require_installed(hud: Path, backups: Path):
    if not backups.exists():
        raise ValueError('HUD 尚未安装汉化。请先退出 RaceRoom，再启动中文游戏。')
    receipt = _receipt(hud, backups)
    if not _verify(hud, backups, receipt):
        raise ValueError('HUD 汉化不完整，请先恢复原版，再启动中文游戏。')
    return receipt


def prepare_launch(game_dir: Path, *, running: bool) -> str:
    """Reuse a verified HUD installation or prepare a new one before Steam starts."""
    if running:
        hud, backups = _layout(game_dir)
        with _locked(backups):
            receipt = _require_installed(hud, backups)
            if receipt.get('hud_version', 1) != HUD_VERSION:
                raise RuntimeError('赛中 HUD 有新版译文。请退出 RaceRoom，再点「一键汉化并启动」更新。')
        return '赛中 HUD 汉化已就绪。'
    return install(game_dir, reuse_existing=True)


def install(game_dir: Path, *, reuse_existing: bool = False) -> str:
    """Back up and translate the selected installation's original HUD."""
    hud, backups = _layout(game_dir)
    with _locked(backups):
        _require_closed()
        previous = None
        if backups.exists():
            if not reuse_existing:
                raise ValueError('已有本地 HUD 备份，请先恢复原版。')
            previous = _require_installed(hud, backups)
            if previous.get('hud_version', 1) == HUD_VERSION:
                return '赛中 HUD 汉化已就绪。'
        previous_panels = previous['panels'] if previous is not None else {}
        _check_unbacked(hud, recipe.PANELS.keys() - previous_panels.keys())
        if not recipe.font_available():
            raise ValueError('缺少可用于 HUD 的 Windows 简体中文字体。')

        game = hud.parents[2]
        executable = _direct(game / 'RRRE64.exe')
        if not executable.is_file():
            executable = _direct(game / 'RRRE.exe')
        labels = recipe.native_labels((executable, _direct(game / 'cosmo.dll')))
        with TemporaryDirectory(prefix='.r3e-hud-install-', dir=_direct(backups.parent)) as temp:
            stage = Path(temp)
            originals = stage / 'originals'
            originals.mkdir()
            paths = {}
            for name in recipe.PANELS:
                paths[name] = originals / f'{name}.json'
                if name in previous_panels:
                    _copy_verified(backups / f'{name}.json', paths[name], previous_panels[name]['original'])
                else:
                    _replace(_manifest(hud, name).read_bytes(), paths[name], None)
            hashes = recipe.prepare(stage, paths, labels=labels)
            font = stage / CUSTOM_FONT
            receipt = {'hud': str(hud), 'hud_version': HUD_VERSION, 'panels': hashes, 'font': recipe.digest(font)}

            # Prepare and verify the new assets before retiring the old installation.
            if previous is not None:
                _restore(hud, backups)

            # Each live file must be original and the font name free before install.
            for name, checksums in hashes.items():
                if _file_hash(_manifest(hud, name)) != checksums['original'] or _font(hud, name).exists():
                    raise ValueError(f'{name} 的 HUD 文件在准备安装期间发生变化。')
            _publish(hud, backups, originals, receipt)
            try:
                for name, checksums in hashes.items():
                    _require_closed()
                    _copy_verified(font, _font(hud, name), receipt['font'])
                    _require_closed()
                    _copy_verified(stage / f'{name}.json', _manifest(hud, name),
                                   checksums['localized'], checksums['original'])
                if not _verify(hud, backups, receipt):
                    raise ValueError('HUD 安装后校验失败。')
            except Exception as exc:
                try:
                    _restore(hud, backups)
                except (OSError, RuntimeError, ValueError) as recovery:
                    raise RuntimeError(f'HUD 安装未完成，已保留备份。{exc} 恢复未完成：{recovery}') from exc
                raise
    return 'HUD 汉化已安装，原版文件已校验并备份。'


def restore(game_dir: Path) -> str:
    """Restore the selected installation, including an interrupted transaction."""
    hud, backups = _layout(game_dir)
    with _locked(backups):
        _require_closed()
        if not backups.exists():
            _check_unbacked(hud, recipe.PANELS)
            return '赛中 HUD 已是原版。'
        _restore(hud, backups)
    return '赛中 HUD 已恢复为原版。'
