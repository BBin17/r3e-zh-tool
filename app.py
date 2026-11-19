"""R3E 中文汉化工具 · 图形界面

运行:  python app.py
打包:  python build_release.py
"""
from __future__ import annotations

import hashlib
import io
import json
import msvcrt
import os
import queue
import re
import subprocess
import sys
import tempfile
import threading
import time
import tkinter as tk
from contextlib import contextmanager
from ctypes import Structure, byref, create_string_buffer, c_void_p, windll, wintypes
from datetime import datetime
from pathlib import Path
import webbrowser
from tkinter import filedialog, messagebox, ttk

# 打包成 exe 后 __file__ 指向临时解压目录，数据文件要放在 exe 所在目录
HERE = (Path(sys.executable).resolve().parent if getattr(sys, "frozen", False)
        else Path(__file__).resolve().parent)
from r3e_jca import JcaFile, Localization  # noqa: E402
from patch import apply_translations, parse_translations  # noqa: E402
from translation_pack import PACK_NAME, bundled_path, parse_pack  # noqa: E402
import updater  # noqa: E402
import setup_tool  # noqa: E402
from steam_depot import InstalledFile, installed_file  # noqa: E402

APP_NAME = setup_tool.APP_NAME
APP_VERSION = setup_tool.APP_VERSION
DEVELOPER = setup_tool.DEVELOPER
PROJECT_URL = f"https://github.com/{updater.GITHUB_REPO}"
QQ_GROUP = "1128386065"

BG = "#EEF1F5"
SURFACE = "#FFFFFF"
WELL = "#F3F4F7"
INK = "#202127"
MUTED = "#5D616D"
RULE = "#DFE0E7"
ACCENT = "#0865CF"
HERO_BG = "#202A39"
HERO_TEXT = "#F5F7FA"
HERO_MUTED = "#C8D2E0"
HERO_GOOD = "#A7E5C0"
HERO_BAD = "#FFC4CB"
LAUNCH_RED = "#A32438"
LAUNCH_HOVER = "#861B2C"
GOOD = "#166749"
BAD = "#A0333D"
WARN = "#865414"

FAMILY = "Microsoft YaHei UI"
UI_LATIN = "Segoe UI Variable Text"

LOC_REL = Path("Game") / "GameData" / "General" / "Localization.jca"
BACKUP_DIRNAME = "zh-patch-backups"
# 只替换这两个语言段。实测：全部 5 段都改成中文后，客户端会把 $KEY 占位符原样显示；
# en_GB + es_ES 两段汉化后，界面正常显示中文，其余段保持官方原文。
INSTALL_LANGS = ("en_GB", "es_ES")


# ---------------------------------------------------------------- 环境探测

def _reg_read(root, path, name):
    try:
        import winreg
        with winreg.OpenKey(root, path) as key:
            return winreg.QueryValueEx(key, name)[0]
    except (OSError, ImportError):
        return None


def steam_libraries() -> list[Path]:
    libs: list[Path] = []
    import winreg
    steam = _reg_read(winreg.HKEY_CURRENT_USER, r"Software\Valve\Steam", "SteamPath")
    if not steam:
        return libs
    root = Path(steam.replace("/", "\\"))
    libs.append(root)
    vdf = root / "steamapps" / "libraryfolders.vdf"
    if vdf.exists():
        text = vdf.read_text(errors="ignore")
        for raw in re.findall(r'"path"\s+"([^"]+)"', text):
            p = Path(raw.replace("\\\\", "\\"))
            if p not in libs:
                libs.append(p)
    return libs


def normalize_game_dir(p: Path) -> Path | None:
    p = Path(p)
    if (p / "Game" / "GameData").is_dir():
        return p
    if p.name.lower() == "game" and (p.parent / "Game" / "GameData").is_dir():
        return p.parent
    return None


def saved_game_dir() -> Path | None:
    ini = Path(os.path.expanduser("~")) / "Documents" / "My Games" / "SimBin" / \
        "RaceRoom Racing Experience" / "GameInstallDir.ini"
    if ini.exists():
        for line in ini.read_text(errors="ignore").splitlines():
            if line.lower().startswith("gameinstalldir="):
                return Path(line.split("=", 1)[1].strip().strip('"'))
    return None


def find_game_dirs() -> list[Path]:
    saved = saved_game_dir()
    cands = [saved] if saved is not None else []
    for lib in steam_libraries():
        cands.append(lib / "steamapps" / "common" / "raceroom racing experience")
    found, seen = [], set()
    for c in cands:
        g = normalize_game_dir(c)
        if g and g not in seen:
            seen.add(g)
            found.append(g)
    return found


def uninstall_game_dirs() -> list[Path]:
    paths = {game.resolve() for game in find_game_dirs()}
    records = setup_tool.install_dir() / "localized-games"
    candidates = [Path(record.read_text(encoding="utf-8")) for record in records.glob("*.txt")]
    saved = saved_game_dir()
    if saved is not None:
        candidates.append(saved)
    for path in candidates:
        if not path.is_absolute():
            raise RuntimeError(f"无法识别已记录的 RaceRoom 路径：{path}")
        if not Path(path.anchor).is_dir():
            raise RuntimeError(f"RaceRoom 所在的磁盘无法访问。请重新连接后再卸载。\n{path}")
        game = normalize_game_dir(path)
        if game is not None:
            paths.add(game.resolve())
        elif path.is_dir():
            raise RuntimeError(f"RaceRoom 安装目录不完整，无法确认汉化状态。\n{path}")
    return sorted(paths)


def restore_before_uninstall() -> None:
    from extra_ui import restore_game_files
    from rr_menu.engine import WatchEvent

    if game_running():
        raise RuntimeError("请先完全退出 RaceRoom，再卸载汉化工具。")
    if setup_tool.tool_running():
        raise RuntimeError("请先退出正在运行的 R3E 汉化工具，再卸载。")

    def ignore(_):
        pass

    event = WatchEvent()
    event.stop()
    with event.own():
        for game in uninstall_game_dirs():
            installer = Installer(game, ignore, ignore)
            results, failed = restore_game_files(game, installer, ignore)
            if failed:
                details = "\n\n".join(results)
                raise RuntimeError(f"游戏目录：{game}\n\n{details}")
        if game_running():
            raise RuntimeError("RaceRoom 已在恢复期间启动，请退出游戏后重试。")


def steam_build_id(game_dir: Path) -> str | None:
    for parent in [game_dir, *game_dir.parents]:
        acf = parent / "steamapps" / "appmanifest_211500.acf"
        if acf.exists():
            for line in acf.read_text(errors="ignore").splitlines():
                if '"buildid"' in line:
                    return line.split('"')[-2]
    return None


class _FixedFileInfo(Structure):
    _fields_ = [("dwSignature", wintypes.DWORD), ("dwStrucVersion", wintypes.DWORD),
                ("dwFileVersionMS", wintypes.DWORD), ("dwFileVersionLS", wintypes.DWORD),
                ("dwProductVersionMS", wintypes.DWORD), ("dwProductVersionLS", wintypes.DWORD),
                ("dwFileFlagsMask", wintypes.DWORD), ("dwFileFlags", wintypes.DWORD),
                ("dwFileOS", wintypes.DWORD), ("dwFileType", wintypes.DWORD),
                ("dwFileSubtype", wintypes.DWORD), ("dwFileDateMS", wintypes.DWORD),
                ("dwFileDateLS", wintypes.DWORD)]


def exe_version(game_dir: Path) -> str | None:
    game = game_dir / "Game"
    exe = next((p for p in (game / "x64" / "RRRE64.exe", game / "RRRE64.exe") if p.is_file()), None)
    if exe is None:
        return None
    size = windll.version.GetFileVersionInfoSizeW(str(exe), None)
    if not size:
        return None
    data = create_string_buffer(size)
    if not windll.version.GetFileVersionInfoW(str(exe), 0, size, data):
        return None
    ptr, length = c_void_p(), wintypes.UINT()
    if not windll.version.VerQueryValueW(data, "\\", byref(ptr), byref(length)):
        return None
    if not ptr.value:
        return None
    fi = _FixedFileInfo.from_address(ptr.value)
    ms, ls = fi.dwFileVersionMS, fi.dwFileVersionLS
    return f"{ms >> 16}.{ms & 0xFFFF}.{ls >> 16}.{ls & 0xFFFF}"


def game_running() -> bool:
    try:
        out = subprocess.run(["tasklist", "/FO", "CSV", "/NH"], capture_output=True,
                             text=True, errors="replace", check=True, timeout=15,
                             creationflags=0x08000000).stdout
        return "RRRE" in out.upper()
    except (OSError, subprocess.SubprocessError) as exc:
        raise RuntimeError("无法确认 RaceRoom 已退出，操作已取消。") from exc


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def has_cjk(text: str) -> bool:
    return any("一" <= ch <= "鿿" for ch in text)


@contextmanager
def staged_file(target: Path):
    """在同一目录内暂存文件，以便校验后原子替换。"""
    with tempfile.NamedTemporaryFile(dir=target.parent, prefix=f".{target.name}-",
                                     suffix=".tmp", delete=False) as handle:
        temp = Path(handle.name)
    try:
        yield temp
    finally:
        temp.unlink(missing_ok=True)


def atomic_write(target: Path, data: bytes) -> None:
    with staged_file(target) as temp:
        temp.write_bytes(data)
        os.replace(temp, target)


def human_size(n: int) -> str:
    return f"{n / 1048576:.2f} MB" if n >= 1048576 else f"{n / 1024:.0f} KB"


# ---------------------------------------------------------------- 业务操作

class Installer:
    def __init__(self, game_dir: Path, log, progress):
        self.game_dir = game_dir
        self.loc_path = game_dir / LOC_REL
        self.backup_dir = self.loc_path.parent / BACKUP_DIRNAME
        self.log = log
        self.progress = progress

    def _manifest(self) -> dict:
        path = self.backup_dir / "manifest.json"
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except FileNotFoundError:
            return {"backups": [], "installs": []}
        except (ValueError, UnicodeError) as exc:
            raise RuntimeError("备份记录无法读取，请保留备份并使用 Steam 验证游戏文件。") from exc
        if not isinstance(data, dict) or any(
            not isinstance(data.get(key), list) or not all(isinstance(row, dict) for row in data[key])
            for key in ("backups", "installs")
        ):
            raise RuntimeError("备份记录格式异常，请保留备份并使用 Steam 验证游戏文件。")
        return data

    def _save_manifest(self, data: dict) -> None:
        atomic_write(self.backup_dir / "manifest.json",
                     json.dumps(data, ensure_ascii=False, indent=2).encode("utf-8"))

    @contextmanager
    def _operation_lock(self):
        self.backup_dir.mkdir(parents=True, exist_ok=True)
        with (self.backup_dir / "operation.lock").open("a+b") as lock:
            lock.seek(0)
            try:
                msvcrt.locking(lock.fileno(), msvcrt.LK_NBLCK, 1)
            except OSError as exc:
                raise RuntimeError("无法锁定游戏备份，请关闭其他汉化工具窗口后重试。") from exc
            yield  # 关闭文件时 Windows 会释放锁。

    def _matching_backup(self, manifest: dict, current_hash: str, build: str | None) -> tuple[dict, bytes] | None:
        for install in reversed(manifest["installs"]):
            if install.get("output_sha256") != current_hash or "build" not in install:
                continue
            if install["build"] != build or not install.get("backup_sha256"):
                continue
            match = self._backup_by_hash(manifest, install["backup_sha256"])
            if match is not None:
                return match
        return None

    def _backup_by_hash(self, manifest: dict, checksum: str) -> tuple[dict, bytes] | None:
        error = None
        for entry in reversed(manifest["backups"]):
            if entry.get("sha256") != checksum:
                continue
            try:
                return entry, self._read_backup(entry)
            except (OSError, RuntimeError) as exc:
                if error is None:
                    error = exc
        if error is not None:
            raise error
        return None

    def _read_backup(self, entry: dict) -> bytes:
        name = entry.get("file")
        if not isinstance(name, str) or Path(name).name != name or not name.endswith(".jca"):
            raise RuntimeError("备份文件名无效，已取消操作。")
        try:
            contents = (self.backup_dir / name).read_bytes()
        except FileNotFoundError as exc:
            raise RuntimeError(f"备份文件缺失：{name}。请使用 Steam 验证游戏文件。") from exc
        if hashlib.sha256(contents).hexdigest() != entry.get("sha256"):
            raise RuntimeError("备份文件校验失败。请使用 Steam 验证游戏文件。")
        return contents

    def _keep_current_backup(self, manifest: dict, keep: dict) -> None:
        if len(manifest["backups"]) <= 1:
            return
        try:
            self._read_backup(keep)
            if (self.backup_dir / keep["file"]).is_symlink():
                self.log("当前备份是文件链接，已跳过清理旧备份。")
                return
        except (OSError, RuntimeError):
            self.log("当前原版备份无法校验，已跳过清理旧备份。")
            return

        remaining = [keep]
        handled = {keep["file"]}
        removed = 0
        for entry in manifest["backups"]:
            name = entry.get("file")
            if isinstance(name, str) and name in handled:
                continue
            try:
                self._read_backup(entry)
            except RuntimeError:
                self.log("一条旧备份记录无法通过校验，已移出可还原列表。")
                continue
            except OSError:
                remaining.append(entry)
                continue
            handled.add(name)
            try:
                (self.backup_dir / name).unlink(missing_ok=True)
            except OSError:
                remaining.append(entry)
                self.log(f"暂时无法清理旧备份，下次将重试：{name}")
            else:
                removed += 1
        try:
            self._save_manifest({**manifest, "backups": remaining})
        except OSError:
            self.log("暂时无法更新旧备份记录，下次将重试。")
        if removed:
            self.log(f"已清理 {removed} 份旧备份，当前原版备份：{keep['file']}")

    def _tidy_matching_backup(self, manifest: dict, current_hash: str, build: str | None) -> None:
        if len(manifest["backups"]) <= 1:
            return
        try:
            match = self._matching_backup(manifest, current_hash, build)
        except (OSError, RuntimeError):
            return
        if match is not None:
            self._keep_current_backup(manifest, match[0])

    def _steam_original(self, build: str) -> InstalledFile | None:
        try:
            libraries = steam_libraries()
        except (OSError, ImportError):
            libraries = []
        return installed_file(self.game_dir, "211500", build, LOC_REL, libraries)

    def _restore_backup(self, manifest: dict, contents: bytes, current_hash: str,
                        build: str | None) -> tuple[dict, bytes, InstalledFile | None] | None:
        match = self._matching_backup(manifest, current_hash, build)
        if match is not None:
            entry, original = match
            return entry, original, None
        if not build or not manifest["backups"] or not any(
            row.get("output_sha256") == current_hash for row in manifest["installs"]
        ):
            return None

        official = self._steam_original(build)
        if official is None or official.matches(contents):
            return None
        for backup in reversed(manifest["backups"]):
            try:
                original = self._read_backup(backup)
            except (OSError, RuntimeError):
                continue
            if official.matches(original):
                return backup, original, official
        return None

    def _require_game_closed(self) -> None:
        if game_running():
            raise RuntimeError("检测到 RaceRoom 正在运行，请先完全退出游戏和启动器。")

    def _require_unchanged(self, current_hash: str, build: str | None) -> None:
        self._require_game_closed()
        if steam_build_id(self.game_dir) != build or sha256_file(self.loc_path) != current_hash:
            raise RuntimeError("操作期间游戏版本或文件发生变化，请重新检测后重试。")

    @staticmethod
    def _verified_match(manifest: dict, current_hash: str, build: str | None) -> dict | None:
        match = manifest.get("localization_match")
        if (isinstance(match, dict) and match.get("version") == 1
                and match.get("languages") == list(INSTALL_LANGS)
                and "build" in match and match["build"] == build
                and match.get("output_sha256") == current_hash
                and type(match.get("pairs")) is int and type(match.get("cjk")) is int
                and 0 <= match["cjk"] <= match["pairs"]):
            return match
        return None

    def inspect(self) -> dict:
        manifest = self._manifest()
        info = {"exists": self.loc_path.is_file(), "size": 0, "cjk": 0, "pairs": 0,
                "backups": len(manifest["backups"]), "build": steam_build_id(self.game_dir),
                "exe": exe_version(self.game_dir), "restorable": False, "patched": False}
        if info["exists"]:
            contents = self.loc_path.read_bytes()
            current_hash = hashlib.sha256(contents).hexdigest()
            info["size"] = len(contents)
            info["mtime"] = datetime.fromtimestamp(self.loc_path.stat().st_mtime).strftime("%Y-%m-%d %H:%M")
            match = self._verified_match(manifest, current_hash, info["build"])
            if match is None:
                localization = Localization.load(JcaFile.from_bytes(contents))
                en = localization.section("en_GB")
                info["pairs"] = len(en.pairs)
                info["cjk"] = sum(1 for _, v in en.pairs if has_cjk(v))
                spanish_patched = any(has_cjk(v) for _, v in localization.section("es_ES").pairs)
            else:
                info["pairs"], info["cjk"] = match["pairs"], match["cjk"]
                spanish_patched = False
            info["patched"] = spanish_patched or info["cjk"] > 0 or any(
                row.get("output_sha256") == current_hash for row in manifest["installs"]
            )
            try:
                restore = self._restore_backup(manifest, contents, current_hash, info["build"])
            except (OSError, RuntimeError):
                restore = None
            if restore is not None:
                info["restorable"] = True
                info["steam_verified"] = restore[2] is not None
        return info

    def install(self, translations_path: Path, *, progress=None) -> dict:
        self._require_game_closed()
        if not translations_path.is_file():
            raise RuntimeError(f"未找到译文表：{translations_path.name}。可在「游戏与文件」中更换译文。")
        if not self.loc_path.is_file():
            raise RuntimeError("未找到 Localization.jca，请重新选择游戏目录。")
        with self._operation_lock():
            return self._install(translations_path, progress or self.progress)

    def _install(self, translations_path: Path, progress) -> dict:
        self._require_game_closed()
        build = steam_build_id(self.game_dir)
        original = self.loc_path.read_bytes()
        original_hash = hashlib.sha256(original).hexdigest()
        table = translations_path.read_bytes()
        table_hash = hashlib.sha256(table).hexdigest()
        manifest = self._manifest()
        match = self._verified_match(manifest, original_hash, build)
        if match is not None and match.get("translations_sha256") == table_hash:
            self.log("基础文本和译文表均未变更，已跳过解密和逐条比对。")
            self._tidy_matching_backup(manifest, original_hash, build)
            progress(100)
            return {"applied": 0, "cached": True}

        if translations_path.suffix.lower() == ".r3ezh":
            translations = parse_pack(table)
        else:
            translations = parse_translations(io.StringIO(table.decode("utf-8-sig"), newline=""))
        if not translations:
            raise RuntimeError("翻译文件里没有有效译文。")
        self.log("解密 Localization.jca …")
        jca = JcaFile.from_bytes(original, lambda i, n: progress(5 + i / n * 40))
        loc = Localization.load(jca)
        targets = [section for section in loc.sections if section.lang in INSTALL_LANGS]
        if sorted(section.lang for section in targets) != sorted(INSTALL_LANGS):
            raise RuntimeError("找不到预期的游戏语言段，已取消安装。")
        contains_cjk = any(has_cjk(value) for section in targets for _, value in section.pairs)
        matched, applied = apply_translations(targets, translations)
        self.log(f"译文匹配 {len(matched):,}/{len(translations):,} 个键，两个语言段共需修改 {applied:,} 条。")
        if not matched:
            raise RuntimeError("译文表与当前游戏文件没有匹配条目，已取消安装。")
        en = loc.section("en_GB")
        verified = {"version": 1, "languages": list(INSTALL_LANGS), "build": build,
                    "translations_sha256": table_hash, "output_sha256": original_hash,
                    "pairs": len(en.pairs), "cjk": sum(1 for _, value in en.pairs if has_cjk(value))}
        if not applied:
            self.log("匹配条目的译文已一致，无需写入。")
            if any(row.get("output_sha256") == original_hash for row in manifest["installs"]):
                self._require_unchanged(original_hash, build)
                manifest["localization_match"] = verified
                try:
                    self._save_manifest(manifest)
                except OSError:
                    self.log("无法保存本次基础文本校验记录，下次启动会重新比对。")
                else:
                    self._tidy_matching_backup(manifest, original_hash, build)
            progress(100)
            return {"applied": 0}

        existing = self._matching_backup(manifest, original_hash, build)
        if existing is None:
            if contains_cjk or any(row.get("output_sha256") == original_hash for row in manifest["installs"]):
                raise RuntimeError("当前文件已被修改，无法确认对应的原版备份。请先使用 Steam 验证游戏文件，再安装汉化。")
            try:
                existing = self._backup_by_hash(manifest, original_hash)
            except (OSError, RuntimeError):
                self.log("同内容的旧备份不可用，将以当前原版文件建立新备份。")

        if existing is not None:
            backup, _ = existing
            self.log(f"原版文件与已有备份完全一致，已复用：{backup['file']}")
        else:
            name = f"Localization-{original_hash[:16]}.jca"
            target = self.backup_dir / name
            try:
                saved_hash = sha256_file(target)
            except FileNotFoundError:
                saved_hash = None
            except OSError:
                saved_hash = ""
            if saved_hash == original_hash:
                self.log(f"已校验并复用上次保存的原版备份：{name}")
            else:
                if saved_hash is not None:
                    stamp = datetime.now().strftime("%Y%m%d-%H%M%S-%f")
                    name = f"Localization-{stamp}-{original_hash[:8]}.jca"
                atomic_write(self.backup_dir / name, original)
                self.log(f"已备份安装前文件：{name}")
            backup = {"file": name, "sha256": original_hash, "cjk": 0,
                      "time": datetime.now().isoformat(timespec="seconds"), "size": len(original)}
            manifest["backups"].append(backup)

        self.log("重新封装、加密并回读校验 …")
        progress(50)
        plain = loc.rebuild()
        with staged_file(self.loc_path) as temp:
            JcaFile(jca.version, plain).dump(temp, lambda i, n: progress(50 + i / n * 40))
            progress(92)
            if JcaFile.load(temp) != JcaFile(jca.version, plain):
                raise RuntimeError("补丁回读校验失败，未替换游戏文件。")
            verified["output_sha256"] = sha256_file(temp)
            manifest["installs"].append({
                "time": datetime.now().isoformat(timespec="seconds"),
                "source": str(translations_path), "applied": applied, "build": build,
                "backup_sha256": backup["sha256"], "output_sha256": verified["output_sha256"],
            })
            manifest["localization_match"] = verified
            # 先写入恢复记录。只有当前游戏文件与输出校验值相同时，记录才可用于恢复。
            self._save_manifest(manifest)
            self._require_unchanged(original_hash, build)
            os.replace(temp, self.loc_path)
        self._keep_current_backup(manifest, backup)
        progress(100)
        self.log(f"安装完成：修改 {applied:,} 条。")
        return {"applied": applied}

    def restore(self) -> str:
        self._require_game_closed()
        if not self.loc_path.is_file():
            raise RuntimeError("未找到 Localization.jca，请使用 Steam 验证游戏文件。")
        with self._operation_lock():
            build = steam_build_id(self.game_dir)
            contents = self.loc_path.read_bytes()
            current_hash = hashlib.sha256(contents).hexdigest()
            manifest = self._manifest()
            restore = self._restore_backup(manifest, contents, current_hash, build)
            if restore is None:
                raise RuntimeError("没有与当前文件及游戏版本匹配的备份。需要恢复时，请使用 Steam 验证游戏文件。")
            entry, original, official = restore
            with staged_file(self.loc_path) as temp:
                temp.write_bytes(original)
                if official is not None and self._steam_original(build) != official:
                    raise RuntimeError("操作期间 Steam 安装清单发生变化，请重新检测后重试。")
                self._require_unchanged(current_hash, build)
                os.replace(temp, self.loc_path)
            self._keep_current_backup(manifest, entry)
        if official is not None:
            self.log("已通过 Steam 当前版本的本地清单核对原版备份。")
        self.log(f"已恢复备份：{entry['file']}")
        return entry["file"]


# ---------------------------------------------------------------- 控件

class ActionButton(tk.Button):
    def __init__(self, parent, text, command, kind, small, size):
        surface = parent.cget("bg")
        base, hover, foreground, border = {
            "primary": (LAUNCH_RED, LAUNCH_HOVER, "#FFFFFF", LAUNCH_RED),
            "secondary": ("#EEF0F4", "#E3E6EC", INK, RULE),
            "ghost": (surface, "#E9ECF2", ACCENT, surface),
        }[kind]
        self.base = base
        self.hover = hover
        self.border = border
        self.disabled_bg = "#354255" if kind == "primary" else "#EBECF0"
        super().__init__(parent, text=text, command=command, bg=base, fg=foreground,
                         activebackground=hover, activeforeground=foreground,
                         disabledforeground=HERO_MUTED if kind == "primary" else "#6D717B", relief="flat", bd=0,
                         highlightthickness=size(1), highlightbackground=border,
                         highlightcolor=ACCENT, takefocus=True, cursor="hand2",
                         font=(FAMILY, -size(12 if small else 13),
                               "normal" if kind == "ghost" else "bold"),
                         padx=size(11 if small else 20), pady=size(4 if small else 10))
        self.bind("<Enter>", lambda _: self._set_hover(True), add="+")
        self.bind("<Leave>", lambda _: self._set_hover(False), add="+")
        self.bind("<Return>", self._activate)

    def _set_hover(self, hovered):
        if self.cget("state") == "normal":
            self.configure(bg=self.hover if hovered else self.base)

    def _activate(self, _event):
        self.invoke()
        return "break"

    def set_enabled(self, enabled: bool):
        state = "normal" if enabled else "disabled"
        if self.cget("state") != state:
            self.configure(state=state, takefocus=enabled,
                           cursor="hand2" if enabled else "arrow",
                           bg=self.base if enabled else self.disabled_bg,
                           highlightbackground=self.border if enabled else self.disabled_bg)


# ---------------------------------------------------------------- 界面

class App:
    def __init__(self, root: tk.Tk):
        self.root = root
        self.scale = max(1.0, root.winfo_fpixels("1i") / 96.0)
        self.events: queue.Queue = queue.Queue()
        self.game_dir: Path | None = None
        self.installer: Installer | None = None
        self.manual_game_dir: Path | None = None
        self.busy = False
        self.detecting = False
        self.can_install = False
        self.basic_patched = False
        self.has_backups = False
        if getattr(sys, "frozen", False):
            self.translations = bundled_path(PACK_NAME)
        else:
            candidates = (bundled_path(PACK_NAME), HERE / "release" / "zh-translations.csv",
                          HERE / "zh-translations.csv", HERE / "R3E-Localization-zh.csv",
                          HERE / "translations" / "zh-translations.csv")
            self.translations = next((path for path in candidates if path.is_file()), HERE / "sample_zh.csv")
        self._pct = 0.0
        self._logged_dir = None
        self.update_busy = False
        self.pending_update: dict | None = None
        self.extras = None
        self.local_build = setup_tool.local_build()
        self.version = f"{APP_VERSION} 本地测试" if self.local_build else APP_VERSION
        self.dialogs: dict[str, tk.Toplevel] = {}
        self._build()
        self._sync_actions()
        self._poll()
        self.root.after(200, self.auto_detect)
        if not self.local_build:
            self.root.after(1500, lambda: self.check_update(manual=False))

    def S(self, n: float) -> int:
        return max(1, int(round(n * self.scale)))

    # -- 构建界面 --------------------------------------------------
    def _label(self, parent, text="", *, size=13, color=INK, font=FAMILY, bold=False, **options):
        return tk.Label(parent, text=text, bg=parent.cget("bg"), fg=color, anchor="w",
                        font=(font, -self.S(size), "bold" if bold else "normal"), **options)

    def _button(self, parent, text, command, kind="ghost", *, small=True):
        return ActionButton(parent, text, command, kind, small, self.S)

    def _display_entry(self, parent, value, *, color=MUTED, font=FAMILY):
        return tk.Entry(parent, textvariable=value, state="readonly", width=1, relief="flat", bd=0,
                        highlightthickness=1, highlightbackground=WELL, highlightcolor=ACCENT,
                        readonlybackground=WELL, fg=color, selectbackground="#DCE9FF",
                        selectforeground=INK, font=(font, -self.S(12)))

    def _row(self, parent):
        return tk.Frame(parent, bg=parent.cget("bg"))

    def _panel(self, parent, *, color=SURFACE, border=RULE):
        outline = self._row(parent)
        backdrop = tk.Canvas(outline, bg=outline.cget("bg"), bd=0, highlightthickness=0,
                             takefocus=False, width=1, height=1)
        backdrop.place(relwidth=1, relheight=1)
        body = tk.Frame(outline, bg=color)
        body.pack(fill="both", expand=True, padx=self.S(18), pady=self.S(12))

        def draw(event):
            backdrop.delete("all")
            w, h = event.width - 1, event.height - 1
            radius = min(self.S(14), w // 2, h // 2)
            if radius < 1:
                return
            points = (radius, 1, w - radius, 1, w, 1, w, radius, w, h - radius,
                      w, h, w - radius, h, radius, h, 1, h, 1, h - radius,
                      1, radius, 1, 1, radius, 1)
            backdrop.create_polygon(points, smooth=True, splinesteps=20, fill=color, outline=border)

        backdrop.bind("<Configure>", draw)
        return outline, body

    def _build(self):
        r = self.root
        r.title(f"{APP_NAME} v{self.version}")
        resources = Path(getattr(sys, "_MEIPASS", HERE))
        try:
            r.iconbitmap(default=str(resources / "app.ico"))
        except tk.TclError:
            pass
        r.configure(bg=BG)
        shell = self._row(r)
        shell.pack(fill="both", expand=True, padx=self.S(19), pady=self.S(16))
        self.shell = shell

        workspace = self._row(shell)
        workspace.pack(fill="both", expand=True)
        hero = self._build_header(workspace, resources)
        panel, body = self._panel(workspace)
        panel.pack(fill="x", pady=(self.S(9), 0))
        self._build_patch_panel(body)
        from extra_ui import ExtraControls

        self.extras = ExtraControls(self, hero, body, steam_libraries, game_running,
                                    status_color=HERO_MUTED)
        self._build_game_panel(workspace)
        self._build_log_panel(workspace)
        self._build_footer(shell, workspace)

        r.update_idletasks()
        min_w, min_h = self._resize_floor()
        w = max(min_w, min(self.S(780), r.winfo_screenwidth() - self.S(32)))
        h = min_h
        x = max(0, (r.winfo_screenwidth() - w) // 2)
        y = max(0, (r.winfo_screenheight() - h) // 2 - self.S(20))
        r.geometry(f"{w}x{h}+{x}+{y}")

    def _resize_floor(self):
        minimum = self.S(670), self.shell.winfo_reqheight() + self.S(34)
        self.root.minsize(*minimum)
        return minimum

    def _build_footer(self, parent, workspace):
        footer = self._row(parent)
        footer.pack(side="bottom", before=workspace, fill="x", pady=(self.S(13), 0))
        self.bar = tk.Canvas(footer, height=self.S(3), bg=RULE, highlightthickness=0, bd=0)
        self.bar.pack(fill="x")
        self.bar.bind("<Configure>", lambda _: self._draw_progress(self._pct))
        line = self._row(footer)
        line.pack(fill="x", pady=(self.S(7), 0))
        self.status = self._label(line, "就绪", size=12, color=MUTED, justify="left",
                                  wraplength=self.S(470))
        self.help_button = self._button(line, "使用说明", self.show_help)
        self.sponsor_button = self._button(line, "赞助", self.show_sponsor)
        self.about_button = self._button(line, "关于", self.show_about)
        self.about_button.pack(side="right")
        self.sponsor_button.pack(side="right", padx=(0, self.S(5)))
        self.help_button.pack(side="right", padx=(0, self.S(5)))
        tools = self._row(line)
        tools.pack(side="right")
        self._build_update_panel(tools)
        self.status.pack(side="left", fill="x", expand=True, padx=(0, self.S(12)))

    def _build_header(self, parent, resources):
        panel, hero = self._panel(parent, color=HERO_BG, border=HERO_BG)
        panel.pack(fill="x")
        header = self._row(hero)
        header.pack(fill="x")
        brand = self._row(header)
        brand.pack(side="left")
        try:
            icon = tk.PhotoImage(file=str(resources / "app-icon-preview.png"))
            self.brand_image = icon.subsample(max(1, round(icon.width() / self.S(44))))
            tk.Label(brand, image=self.brand_image, bg=HERO_BG, bd=0).pack(
                side="left", padx=(0, self.S(12)))
        except tk.TclError:
            pass
        heading = self._row(brand)
        heading.pack(side="left")
        self._label(heading, APP_NAME, size=23, bold=True, color=HERO_TEXT).pack(anchor="w")
        self._label(heading, "RaceRoom Racing Experience", size=13, color=HERO_MUTED,
                    font=UI_LATIN).pack(anchor="w")
        self._label(header, f"v{self.version}", size=12, color=HERO_MUTED).pack(side="right", anchor="n")

        launch = self._row(hero)
        launch.pack(fill="x", pady=(self.S(14), 0))
        return launch

    def _expandable_panel(self, parent, title, *, expand=False):
        panel, body = self._panel(parent)
        panel.pack(fill="both" if expand else "x", expand=expand, pady=(self.S(8), 0))
        heading = self._row(body)
        heading.pack(fill="x")
        self._label(heading, title, size=13, bold=True).pack(side="left")
        content = self._row(body)
        toggle = self._button(heading, "展开", lambda: self._toggle_section(content, toggle))
        toggle.pack(side="right")
        return content

    def _build_game_panel(self, parent):
        body = self._expandable_panel(parent, "游戏与文件")

        folder = self._row(body)
        folder.pack(fill="x", pady=(self.S(5), self.S(5)))
        self.btn_detect = self._button(folder, "重新检测", self.redetect_game)
        self.btn_detect.pack(side="right")
        self.btn_folder = self._button(folder, "选择游戏目录", self.choose_game_dir)
        self.btn_folder.pack(side="right")
        self.path_var = tk.StringVar()
        self._display_entry(folder, self.path_var).pack(side="left", fill="x", expand=True,
                                                        ipady=self.S(4), padx=(0, self.S(6)))

        details = self._row(body)
        details.pack(fill="x")
        self.build_label = self._label(details, "读取中…", size=11, color=MUTED, font=UI_LATIN)
        self.build_label.pack(side="left", padx=(0, self.S(8)))
        self.stat_vars = {}
        for key, caption in (("total", "原文"), ("done", "中文"), ("backup", "备份"), ("size", "大小")):
            var = self.stat_vars[key] = tk.StringVar(value="—")
            self._label(details, caption, size=11, color=MUTED).pack(side="left", padx=(self.S(8), 0))
            self._label(details, textvariable=var, size=11, font=UI_LATIN).pack(side="left")
        self.meta_label = self._label(details, size=11, color=MUTED)
        self.meta_label.pack(side="right", padx=(self.S(8), 0))

        file_row = self._row(body)
        file_row.pack(fill="x", pady=(self.S(8), 0))
        self._label(file_row, "翻译文件", size=12, color=MUTED).pack(side="left", padx=(0, self.S(8)))
        self._button(file_row, "创建桌面快捷方式", self.create_desktop_shortcut).pack(side="right")
        self.btn_open = self._button(file_row, "备份目录", self.open_backups)
        self.btn_open.pack(side="right")
        self.btn_csv = self._button(file_row, "更换译文表", self.choose_csv)
        self.btn_csv.pack(side="right")
        self.csv_var = tk.StringVar(value=self.translations.name)
        self._display_entry(file_row, self.csv_var, color=INK, font=UI_LATIN).pack(
            side="left", fill="x", expand=True, ipady=self.S(4))

    def _build_log_panel(self, parent):
        self.log_frame = self._expandable_panel(parent, "操作日志", expand=True)
        self.log_text = tk.Text(self.log_frame, bg=WELL, fg=INK, bd=0, relief="flat", wrap="word",
                                font=(FAMILY, -self.S(12)), height=4, width=1,
                                padx=self.S(9), pady=self.S(7), spacing3=self.S(2),
                                selectbackground="#DCE9FF", selectforeground=INK, state="disabled",
                                highlightthickness=1, highlightbackground=RULE, highlightcolor=ACCENT)
        style = ttk.Style(self.log_frame)
        style.configure("Log.Vertical.TScrollbar", background=RULE, troughcolor=WELL,
                        bordercolor=WELL, lightcolor=RULE, darkcolor=RULE,
                        arrowcolor=MUTED, arrowsize=self.S(9), gripcount=0)
        style.map("Log.Vertical.TScrollbar", background=[("active", "#BCC0CA")])
        scrollbar = ttk.Scrollbar(self.log_frame, command=self.log_text.yview, style="Log.Vertical.TScrollbar")
        self.log_text.configure(yscrollcommand=scrollbar.set)
        self.log_text.tag_configure("timestamp", foreground=MUTED)
        scrollbar.pack(side="right", fill="y")
        self.log_text.pack(side="left", fill="both", expand=True)

    def _toggle_section(self, content, toggle):
        old_minimum = self.root.minsize()[1]
        old_height = self.root.winfo_height()
        expanded = bool(content.winfo_manager())
        if expanded:
            content.pack_forget()
        else:
            content.pack(fill="both", expand=True, pady=(self.S(6), 0))
            if content is self.log_frame:
                self.log_text.see("end")
        toggle.configure(text="展开" if expanded else "收起")
        self.root.update_idletasks()
        _, minimum = self._resize_floor()
        height = max(minimum, old_height + minimum - old_minimum)
        self.root.geometry(f"{self.root.winfo_width()}x{height}")

    def _build_patch_panel(self, body):
        summary = self._row(body)
        summary.pack(side="left", fill="x", expand=True, padx=(0, self.S(14)))
        heading = self._row(summary)
        heading.pack(anchor="w")
        self._label(heading, "基础文本", size=15, bold=True).pack(side="left")
        self.basic_state = self._label(heading, "等待检测", size=12, color=MUTED, bold=True)
        self.basic_state.pack(side="left", padx=(self.S(10), 0))
        self.basic_summary = self._label(summary, size=12, color=MUTED, justify="left",
                                         wraplength=self.S(420))
        self.basic_summary.pack(anchor="w", pady=(self.S(3), 0))

    def _open_info(self, title):
        existing = self.dialogs.get(title)
        if existing is not None:
            existing.deiconify()
            existing.lift()
            existing.focus_set()
            return None
        window = tk.Toplevel(self.root)
        self.dialogs[title] = window
        window.withdraw()
        window.title(title)
        window.transient(self.root)
        window.resizable(False, False)
        window.configure(bg=SURFACE)
        body = self._row(window)
        body.pack(fill="both", padx=self.S(24), pady=self.S(20))
        self._label(body, title, size=24, bold=True).pack(anchor="w", pady=(0, self.S(12)))
        return window, body

    def _show_info(self, window, body, *, primary_action=None):
        title = window.title()

        def close():
            self.dialogs.pop(title, None)
            window.destroy()

        window.protocol("WM_DELETE_WINDOW", close)
        window.bind("<Escape>", lambda _: close())
        actions = self._row(body)
        actions.pack(anchor="e", pady=(self.S(14), 0))
        if primary_action is not None:
            label, command = primary_action

            def proceed():
                close()
                command()

            self._button(actions, label, proceed, "secondary").pack(side="right")
        close_button = self._button(actions, "关闭", close, "ghost" if primary_action else "secondary")
        close_button.pack(side="right")
        window.update_idletasks()
        width, height = window.winfo_reqwidth(), window.winfo_reqheight()
        x = self.root.winfo_rootx() + (self.root.winfo_width() - width) // 2
        y = self.root.winfo_rooty() + (self.root.winfo_height() - height) // 2
        window.geometry(f"{width}x{height}+{max(0, x)}+{max(0, y)}")
        window.deiconify()
        close_button.focus_set()

    def show_help(self):
        opened = self._open_info("使用说明")
        if opened is None:
            return
        window, body = opened
        sections = [("选择游戏目录", "工具会自动查找 Steam 游戏目录。\n未找到时，点「选择游戏目录」。")]
        sections.extend((
            ("一键汉化并启动", "退出游戏后点击主按钮。工具会检查基础文本，必要时备份并写入译文，再准备赛中 HUD 并通过 Steam 启动。游玩时请保持工具开启，让网页菜单自动汉化。"),
            ("基础文本未完成", "如果译文缺失或不匹配，可以更换译文表，也可以按提示仅启用菜单与 HUD 并启动。"),
            ("恢复原版", "退出游戏后点「恢复原版」，查看网页菜单、赛中 HUD 和基础文本的恢复结果。若提示原版备份未匹配，请在 Steam 验证游戏文件。"),
        ))
        for heading, text in sections:
            self._label(body, heading, size=14, bold=True).pack(anchor="w", pady=(self.S(5), 0))
            self._label(body, text, size=13, color=MUTED, wraplength=self.S(420), justify="left").pack(
                fill="x", pady=(0, self.S(7)))
        self._show_info(window, body)

    def show_about(self):
        opened = self._open_info("关于")
        if opened is None:
            return
        window, body = opened
        self._label(body, APP_NAME, size=17, bold=True).pack(anchor="w")
        self._label(body, f"版本 v{self.version}", size=13, color=MUTED).pack(anchor="w")
        self._label(body, f"开发者 {DEVELOPER}", size=13, color=MUTED).pack(anchor="w", pady=(self.S(4), 0))
        group = self._row(body)
        group.pack(anchor="w", pady=(self.S(6), self.S(6)))
        self._label(group, f"QQ 交流群  {QQ_GROUP}", size=13).pack(side="left")

        def copy_group():
            window.clipboard_clear()
            window.clipboard_append(QQ_GROUP)
            copy_button.configure(text="已复制")

        copy_button = self._button(group, "复制群号", copy_group)
        copy_button.pack(side="left", padx=(self.S(5), 0))

        def open_github(url):
            try:
                if webbrowser.open_new_tab(url):
                    return
            except (OSError, webbrowser.Error):
                pass
            messagebox.showwarning("打开 GitHub", f"无法打开默认浏览器。请访问：\n{url}", parent=window)

        links = self._row(body)
        links.pack(anchor="w")
        self._button(links, "GitHub 发布页", lambda: open_github(f"{PROJECT_URL}/releases")).pack(side="left")
        self._button(links, "使用条款", lambda: open_github(f"{PROJECT_URL}#源码与授权")).pack(side="left")

        self._show_info(window, body)

    def show_sponsor(self):
        opened = self._open_info("赞助")
        if opened is None:
            return
        window, body = opened
        thanks = self._label(body, "感谢你使用 R3E\u00a0汉化工具！", size=14, bold=True,
                             justify="left", padx=0, wraplength=self.S(300))
        thanks.pack(fill="x", pady=(0, self.S(5)))
        invitation = self._label(body, "如果汉化让你玩得更顺手，欢迎随心支持后续的翻译和维护。",
                                 size=13, color=MUTED, justify="left", padx=0,
                                 wraplength=self.S(300))
        invitation.pack(fill="x", pady=(0, self.S(14)))
        card_dir = Path(getattr(sys, "_MEIPASS", HERE)) / "docs" / "images" / "donate"
        try:
            cards = [tk.PhotoImage(master=window, file=str(card_dir / name))
                     for name in ("wechat-card.png", "alipay-card.png")]
        except tk.TclError:
            self._label(body, "赞助二维码加载失败，请在 GitHub 项目页面查看。", color=MUTED).pack(anchor="w")
        else:
            window.update_idletasks()
            gap = self.S(10)
            card_width = max(1, min(self.S(250), (window.winfo_screenwidth() - self.S(64) - gap) // 2))
            card_height = max(1, window.winfo_screenheight() - window.winfo_reqheight() - self.S(96))
            row = self._row(body)
            row.pack(anchor="w")
            for index, card in enumerate(cards):
                factor = max((card.width() + card_width - 1) // card_width,
                             (card.height() + card_height - 1) // card_height)
                image = card.subsample(factor)
                label = tk.Label(row, image=image, bg=SURFACE, bd=0, highlightthickness=0)
                label.image = image
                label.pack(side="left", padx=(gap if index else 0, 0))
            window.update_idletasks()
            content_width = row.winfo_reqwidth()
            thanks.configure(wraplength=content_width)
            invitation.configure(wraplength=content_width)

        self._show_info(window, body)

    def _build_update_panel(self, body):
        actions = self._row(body)
        actions.pack(fill="x")
        self.update_label = self._label(actions, "", size=11, color=MUTED)
        self.update_label.pack(side="left")
        self.btn_update_notice = self._button(actions, "", self._show_update_notice)
        self.btn_update_notice.configure(font=(FAMILY, -self.S(11), "underline"), padx=self.S(4))
        self.btn_check = self._button(actions, "检查更新", lambda: self.check_update(True))
        self.btn_check.pack(side="right")
        update_text = "前往下载" if self.local_build else "下载更新"
        self.btn_update = self._button(actions, update_text, self.do_update, "secondary")

    def _draw_progress(self, pct):
        c = getattr(self, "bar", None)
        if c is None:
            return
        c.delete("all")
        w = c.winfo_width() or 1
        h = self.S(3)
        c.create_rectangle(0, 0, w, h, fill=RULE, outline="")
        if pct > 0:
            c.create_rectangle(0, 0, w * pct / 100, h, fill=ACCENT, outline="")

    def set_progress(self, pct: float):
        self._pct = max(0.0, min(100.0, pct))
        self._draw_progress(self._pct)

    # -- 线程与事件 --------------------------------------------------
    def _poll(self):
        try:
            while True:
                kind, payload = self.events.get_nowait()
                if kind == "log":
                    self._append_log(payload)
                elif kind == "progress":
                    self.set_progress(payload)
                elif kind == "status":
                    self.status.configure(text=payload)
                elif kind == "state":
                    self._apply_state(payload)
                elif kind == "done":
                    self._finish(payload)
                elif kind == "error":
                    self._fail(payload)
                elif kind == "update_info":
                    self._on_update_info(payload)
                elif kind == "update_failed":
                    self._on_update_failed(payload)
                elif kind == "update_ready":
                    self._apply_downloaded(payload)
                elif kind == "extras":
                    callback, args = payload
                    callback(*args)
        except queue.Empty:
            pass
        self.root.after(80, self._poll)

    def _append_log(self, msg: str):
        ts = time.strftime("%H:%M:%S")
        self.log_text.configure(state="normal")
        self.log_text.insert("end", f"{ts}  ", "timestamp")
        self.log_text.insert("end", f"{msg}\n")
        self.log_text.see("end")
        self.log_text.configure(state="disabled")

    def log(self, msg: str):
        self.events.put(("log", msg))

    def progress(self, pct: float):
        self.events.put(("progress", pct))

    def _sync_actions(self):
        ready = not self.busy and not self.detecting
        self.btn_folder.set_enabled(ready)
        self.btn_detect.set_enabled(ready)
        self.btn_csv.set_enabled(ready)
        self.btn_open.set_enabled(ready and self.has_backups)
        if self.extras is not None:
            self.extras.sync_actions()

    def _set_busy(self, busy: bool):
        self.busy = busy
        self._sync_actions()

    def _finish(self, message: str):
        self._set_busy(False)
        self.status.configure(text=message)
        self.set_progress(100)
        self.auto_detect(silent=True)

    def _fail(self, message: str):
        self._set_busy(False)
        self.status.configure(text="操作失败")
        self.set_progress(0)
        self._append_log("错误: " + message)
        messagebox.showerror(APP_NAME, message)

    # -- 动作 --------------------------------------------------
    def auto_detect(self, silent=False):
        if self.busy or self.detecting:
            return
        self.detecting = True
        self._sync_actions()
        self._set_state("正在检测游戏…", "正在查找 RaceRoom 安装目录", MUTED)
        if not silent:
            self._append_log("正在检测游戏目录 …")
        manual_game = self.manual_game_dir

        def work():
            game = manual_game
            try:
                if game is None:
                    dirs = find_game_dirs()
                    game = next((p for p in dirs if (p / LOC_REL).is_file()), dirs[0] if dirs else None)
                if game is None:
                    self.events.put(("state", {"dir": None, "silent": silent}))
                    return
                inst = Installer(game, self.log, self.progress)
                if not silent:
                    self.events.put(("status", "正在读取 Localization.jca …"))
                info = inst.inspect()
            except Exception as exc:  # noqa: BLE001
                self.events.put(("state", {"dir": game, "error": str(exc)}))
                return
            self.events.put(("state", {"dir": game, "info": info, "installer": inst, "silent": silent}))

        threading.Thread(target=work, daemon=True).start()

    def choose_game_dir(self):
        if self.busy or self.detecting:
            return
        path = filedialog.askdirectory(title="选择 RaceRoom 游戏目录", mustexist=True,
                                       initialdir=str(self.game_dir or Path.home()))
        if not path:
            return
        game = normalize_game_dir(Path(path))
        if game is None or not (game / LOC_REL).is_file():
            messagebox.showerror(APP_NAME, "所选目录没有 Localization.jca。请选择 Steam 中的 RaceRoom 安装目录。")
            return
        self.manual_game_dir = game
        self.auto_detect()

    def redetect_game(self):
        if self.busy or self.detecting:
            return
        self.manual_game_dir = None
        self.auto_detect()

    def record_localized_game(self, game: Path) -> None:
        directory = setup_tool.install_dir().resolve()
        if HERE != directory:
            return
        path = str(game.resolve())
        records = directory / "localized-games"
        records.mkdir(exist_ok=True)
        name = hashlib.sha256(path.casefold().encode("utf-8")).hexdigest()
        atomic_write(records / f"{name}.txt", path.encode("utf-8"))

    def _set_state(self, title, desc, color, meta=""):
        if self.extras is not None:
            self.extras.game_status.configure(text=title, fg={GOOD: HERO_GOOD, BAD: HERO_BAD}.get(color, HERO_MUTED))
        self.path_var.set(desc)
        self.meta_label.configure(text=meta)

    def _apply_state(self, payload: dict):
        game = payload.get("dir")
        info = payload.get("info", {})
        self.detecting = False
        self.game_dir = game
        self.installer = payload.get("installer")
        self.can_install = bool(info.get("exists"))
        self.basic_patched = bool(info.get("patched"))
        self.has_backups = bool(info.get("backups"))
        self._sync_actions()
        self.set_progress(0)
        for var in self.stat_vars.values():
            var.set("—")
        if "error" in payload:
            self.build_label.configure(text="读取失败")
            self.basic_state.configure(text="读取失败", fg=BAD)
            self.basic_summary.configure(text="展开「游戏与文件」查看详情。")
            self._set_state("状态读取失败", payload["error"], BAD)
            self.status.configure(text="可重新检测或选择游戏目录")
            return
        if game is None:
            self.build_label.configure(text="未检测到安装")
            self.basic_state.configure(text="等待选择游戏", fg=MUTED)
            self.basic_summary.configure(text="")
            self._set_state("未检测到 RaceRoom", "请确认游戏已通过 Steam 安装，或手动选择目录。", BAD)
            self.status.configure(text="等待选择游戏目录")
            return
        self.build_label.configure(
            text=f"Build {info.get('build') or '—'}  |  RRRE64 {info.get('exe') or '—'}")
        if not self.can_install:
            self.basic_state.configure(text="缺少游戏文本", fg=BAD)
            self.basic_summary.configure(text="未找到 Localization.jca")
            self._set_state("已检测到 RaceRoom", str(game), GOOD)
            self.status.configure(text="请检查游戏目录或通过 Steam 验证文件。")
            return
        cjk = info["cjk"]
        if info["patched"]:
            if info.get("steam_verified"):
                backup_status = "原版备份与 Steam 当前版本一致"
            else:
                backup_status = "可使用本机备份还原" if info["restorable"] else "原版备份未匹配"
            self.basic_state.configure(text="已汉化", fg=GOOD)
        else:
            backup_status = f"文件修改于 {info['mtime']}"
            self.basic_state.configure(text="未安装", fg=MUTED)
        self._set_state("已检测到 RaceRoom", str(game), GOOD, backup_status)
        self.basic_summary.configure(text=f"{cjk:,} 条中文译文 · {info['backups']:,} 份原版备份")
        self.stat_vars["total"].set(f"{info['pairs']:,}")
        self.stat_vars["done"].set(f"{cjk:,}")
        self.stat_vars["backup"].set(f"{info['backups']}")
        self.stat_vars["size"].set(human_size(info["size"]))
        if self._logged_dir != game:
            self._logged_dir = game
            self._append_log(f"游戏目录: {game}")
            self._append_log(f"Localization.jca: {info['size']:,} 字节，中文条目 {cjk}")
        if info["patched"] and not info["restorable"]:
            self.status.configure(text="没有匹配的原版备份。需要恢复时，请使用 Steam 验证游戏文件。")
        elif not payload.get("silent"):
            self.status.configure(text="就绪")

    def choose_csv(self):
        path = filedialog.askopenfilename(title="选择翻译文件",
                                          filetypes=[("译文包或自定义 CSV", ("*.r3ezh", "*.csv"))])
        if path:
            self.translations = Path(path)
            self.csv_var.set(Path(path).name)

    def open_backups(self):
        if not self.installer:
            return
        self.installer.backup_dir.mkdir(parents=True, exist_ok=True)
        os.startfile(self.installer.backup_dir)  # noqa: S606

    def _start(self, message: str):
        self._set_busy(True)
        self.set_progress(0)
        self.status.configure(text=message)
        self._append_log(message)

    def create_desktop_shortcut(self):
        if not getattr(sys, "frozen", False):
            messagebox.showinfo(APP_NAME, "请使用安装版或打包后的程序创建快捷方式。")
            return
        try:
            link = setup_tool.desktop_shortcut_path()
            setup_tool.make_shortcut(link, Path(sys.executable).resolve())
        except (OSError, RuntimeError) as exc:
            messagebox.showerror(APP_NAME, f"创建桌面快捷方式失败：{exc}")
            return
        messagebox.showinfo(APP_NAME, f"已创建桌面快捷方式：\n{link}")

    # -- 程序更新（检查 GitHub Releases）-----------------------------
    def check_update(self, manual: bool = False):
        if self.update_busy:
            return
        self.update_busy = True
        if self.pending_update is None:
            self.update_label.configure(text="正在检查更新…", fg=MUTED)

        def work():
            try:
                info = updater.check(APP_VERSION)
                self.events.put(("update_info", (info, manual)))
            except updater.UpdateError as exc:
                self.events.put(("update_failed", (str(exc), manual)))
            except Exception as exc:  # noqa: BLE001
                self.events.put(("update_failed", (f"检查更新失败：{exc}", manual)))

        threading.Thread(target=work, daemon=True).start()

    def _on_update_info(self, payload):
        info, manual = payload
        self.update_busy = False
        previous = self.dialogs.pop("发现新版本", None)
        if previous is not None:
            previous.destroy()
        if info["newer"]:
            self.pending_update = info
            self.update_label.pack_forget()
            self.btn_update_notice.configure(text=f"发现新版本 {info['tag']}")
            self.btn_update_notice.pack(side="left")
            if not self.btn_update.winfo_manager():
                self.btn_update.pack(side="right", padx=(0, self.S(5)))
            self._append_log(f"发现新版本 {info['tag']}（当前 v{APP_VERSION}）")
            self._show_update_notice()
        else:
            self.pending_update = None
            self.btn_update_notice.pack_forget()
            self.btn_update.pack_forget()
            self.update_label.configure(text="未发现新版本", fg=MUTED)
            self.update_label.pack(side="left")
            if manual:
                messagebox.showinfo(APP_NAME, f"当前版本为 v{APP_VERSION}，未发现新版本。")

    def _show_update_notice(self):
        info = self.pending_update
        if info is None:
            return
        opened = self._open_info("发现新版本")
        if opened is None:
            return
        window, body = opened
        self._label(body, info["tag"], size=16, bold=True).pack(anchor="w", pady=(0, self.S(8)))
        content = (info.get("notes") or "").strip()
        if content:
            panel = self._row(body)
            panel.pack(fill="x")
            notes = tk.Text(panel, width=48, height=12, wrap="word", bg=WELL, fg=INK,
                            bd=0, padx=self.S(10), pady=self.S(8), spacing3=self.S(4),
                            font=(FAMILY, -self.S(13)), highlightthickness=0)
            scrollbar = ttk.Scrollbar(panel, orient="vertical", command=notes.yview)
            notes.configure(yscrollcommand=scrollbar.set)
            scrollbar.pack(side="right", fill="y")
            notes.pack(side="left", fill="both", expand=True)
            notes.tag_configure("heading", font=(FAMILY, -self.S(14), "bold"))
            for line in content.splitlines():
                heading = re.match(r"^#{1,6}\s+(.+)$", line)
                if heading:
                    notes.insert("end", heading[1] + "\n", "heading")
                else:
                    notes.insert("end", re.sub(r"^(\s*)[-*+]\s+", r"\1• ", line) + "\n")
            notes.configure(state="disabled")
        else:
            self._label(body, "此版本未填写更新说明。", color=MUTED).pack(anchor="w")
        self._button(body, "在 GitHub 查看发布页",
                     lambda: webbrowser.open_new_tab(info["url"])).pack(anchor="w", pady=(self.S(5), 0))
        action = None if self.local_build else ("下载更新", self.do_update)
        self._show_info(window, body, primary_action=action)

    def _on_update_failed(self, payload):
        message, manual = payload
        self.update_busy = False
        if self.pending_update is None:
            self.update_label.configure(text="更新检查未完成", fg=WARN)
        self._append_log("更新检查: " + message)
        if manual:
            messagebox.showwarning(APP_NAME, message)

    def do_update(self):
        info = self.pending_update
        if not info:
            return
        if self.local_build or not getattr(sys, "frozen", False):
            webbrowser.open(info["url"])
            return
        if self.busy:
            messagebox.showwarning(APP_NAME, "当前有操作在进行，请稍后再更新。")
            return
        if not messagebox.askyesno(
                APP_NAME, f"下载 {info['tag']} 并替换当前程序，完成后自动重新打开。\n继续吗？"):
            return
        self._start(f"正在下载 {info['tag']} …")
        target_dir = Path(sys.executable).resolve().parent

        def work():
            try:
                new = updater.download_update(
                    info, target_dir, lambda pct: self.events.put(("progress", pct)))
                self.events.put(("update_ready", new))
            except updater.UpdateError as exc:
                self.events.put(("error", str(exc)))
            except Exception as exc:  # noqa: BLE001
                self.events.put(("error", f"下载更新失败：{exc}"))

        threading.Thread(target=work, daemon=True).start()

    def _apply_downloaded(self, new: dict):
        try:
            updater.apply_update(Path(new["exe"]), new["sha256"])
        except (updater.UpdateError, OSError) as exc:
            self._fail(str(exc))
            return
        self._append_log("新版本已下载并校验通过，正在重新启动…")
        self.root.after(400, self.root.destroy)


def enable_dpi_awareness() -> None:
    try:
        windll.shcore.SetProcessDpiAwareness(2)
    except Exception:  # noqa: BLE001
        try:
            windll.user32.SetProcessDPIAware()
        except Exception:  # noqa: BLE001
            pass


def main() -> None:
    if len(sys.argv) == 6 and sys.argv[1] == "--update-helper":
        raise SystemExit(updater.run_update_helper(sys.argv[2:]))
    if sys.argv[1:] == ["--uninstall-installed"]:
        enable_dpi_awareness()
        root = tk.Tk()
        root.withdraw()
        try:
            raise SystemExit(setup_tool.uninstall_interactive(restore_before_uninstall, parent=root))
        finally:
            root.destroy()
    if len(sys.argv) >= 3 and sys.argv[1] == "--cleanup-update-helper":
        threading.Thread(target=updater.cleanup_helper, args=(sys.argv[2],), daemon=True).start()
    selftest = "--selftest" in sys.argv
    enable_dpi_awareness()
    root = tk.Tk()
    root.withdraw()
    app = App(root)
    root.deiconify()
    if selftest:
        buttons = [app.btn_check, app.help_button, app.sponsor_button, app.about_button]
        from extra_ui import probe

        if getattr(sys, "frozen", False):
            parse_pack(app.translations.read_bytes())
        probe()
        buttons.extend((app.extras.start_game, app.extras.restore_game))
        root.update()
        if any(button.winfo_toplevel() is not root or not button.winfo_viewable() for button in buttons):
            raise RuntimeError("主窗口未显示所需的操作按钮。")
        root.after(1500, root.destroy)
    root.mainloop()
    if selftest:
        print("SELFTEST OK")


if __name__ == "__main__":
    main()
