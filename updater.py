"""检查 GitHub Releases 上的新版本，下载并替换当前程序。

每个版本发布程序、安装包及带 Ed25519 签名的 SHA256 清单。
译文包随程序一起更新。
Release 的标签名形如 v0.3，版本号取其中的数字。
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import subprocess
import sys
import shutil
import tempfile
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Callable

from translation_pack import MANIFEST_DOMAIN, verify_signature

# 更新查询指向公开发布仓库，供用户直接读取 Releases。
GITHUB_REPO = "BBin17/r3e-zh-tool"
EXE_NAME = "R3E-ZH-Tool.exe"
SETUP_NAME = "R3E-ZH-Tool-Setup.exe"
SUMS_NAME = "SHA256SUMS.txt"
SUMS_SIGNATURE_NAME = "SHA256SUMS.sig"
LEGACY_CSV_NAME = "zh-translations.csv"
LEGACY_CSV_CONTENT = b"key,zh\n"
LEGACY_EXE_DOWNLOAD = "R3E-ZH-Tool.new.exe"
LEGACY_CSV_DOWNLOAD = "zh-translations.new.csv"
API_URL = "https://api.github.com/repos/{repo}/releases/latest"
USER_AGENT = "R3E-ZH-Tool-updater"


class UpdateError(RuntimeError):
    """可以直接展示给用户的更新错误。"""


def parse_version(text: str) -> tuple[int, ...]:
    nums = [int(n) for n in re.findall(r"\d+", text or "")][:4]
    return tuple(nums) or (0,)


def is_newer(remote: str, local: str) -> bool:
    a, b = parse_version(remote), parse_version(local)
    width = max(len(a), len(b))
    return a + (0,) * (width - len(a)) > b + (0,) * (width - len(b))


def _request(url: str, timeout: float):
    req = urllib.request.Request(url, headers={
        "User-Agent": USER_AGENT,
        "Accept": "application/vnd.github+json",
    })
    return urllib.request.urlopen(req, timeout=timeout)


def _read_small(url: str) -> bytes:
    try:
        with _request(url, 15) as resp:
            return resp.read()
    except urllib.error.HTTPError as exc:
        if exc.code == 404:
            raise UpdateError("仓库里还没有发布版本。") from exc
        raise UpdateError(f"GitHub 返回错误 {exc.code}。") from exc
    except (urllib.error.URLError, OSError) as exc:
        raise UpdateError(f"无法连接 GitHub：{getattr(exc, 'reason', exc)}") from exc


def check(local_version: str, repo: str = GITHUB_REPO) -> dict:
    """返回 {"tag", "url", "newer", "assets", "notes"}。网络或仓库问题抛出 UpdateError。"""
    if "/" not in repo or repo.upper().startswith("OWNER/"):
        raise UpdateError("尚未配置更新仓库（updater.py 里的 GITHUB_REPO）。")
    data = json.loads(_read_small(API_URL.format(repo=repo)).decode("utf-8"))
    tag = data.get("tag_name") or ""
    assets = {a["name"]: a["browser_download_url"] for a in data.get("assets", [])}
    return {
        "tag": tag,
        "url": data.get("html_url") or f"https://github.com/{repo}/releases",
        "newer": is_newer(tag, local_version),
        "assets": assets,
        "notes": data.get("body") or "",
    }


def manifest_header(tag: str) -> str:
    if not re.fullmatch(r"v[0-9]+(?:\.[0-9]+){1,3}", tag):
        raise ValueError("发布标签格式无效。")
    return f"# R3E release {tag}\n"


def _release_checksum(info: dict) -> str:
    assets = info["assets"]
    required = (EXE_NAME, SUMS_NAME, SUMS_SIGNATURE_NAME)
    missing = [name for name in required if not assets.get(name)]
    if missing:
        raise UpdateError(f"发布版本缺少附件：{'、'.join(missing)}。已取消更新。")
    manifest = _read_small(assets[SUMS_NAME])
    signature = _read_small(assets[SUMS_SIGNATURE_NAME])
    try:
        verify_signature(MANIFEST_DOMAIN + manifest, signature)
        if not manifest.startswith(manifest_header(info["tag"]).encode("ascii")):
            raise ValueError("签名清单与发布版本不一致。")
        rows = manifest.decode("ascii").splitlines()[1:]
        digests = [parts[0] for line in rows if len(parts := line.split()) == 2 and parts[1] == EXE_NAME]
        if len(digests) != 1 or not re.fullmatch(r"[0-9a-f]{64}", digests[0]):
            raise ValueError("签名清单中的程序校验值无效。")
    except ValueError as exc:
        raise UpdateError(str(exc)) from exc
    return digests[0]


def _download_verified(url: str, name: str, expected: str, target: Path,
                       progress: Callable[[float], None] | None = None) -> Path:
    digest = hashlib.sha256()
    try:
        with _request(url, 60) as resp, open(target, "wb") as fh:
            total = int(resp.headers.get("Content-Length") or 0)
            done = 0
            while True:
                chunk = resp.read(64 * 1024)
                if not chunk:
                    break
                fh.write(chunk)
                digest.update(chunk)
                done += len(chunk)
                if progress and total:
                    progress(done / total * 100)
    except (urllib.error.URLError, OSError) as exc:
        target.unlink(missing_ok=True)
        raise UpdateError(f"下载失败：{getattr(exc, 'reason', exc)}") from exc
    if digest.hexdigest() != expected:
        target.unlink(missing_ok=True)
        raise UpdateError(f"{name} 校验失败，已删除，未做任何替换。")
    return target


def download_update(info: dict, dest_dir: Path,
                    progress: Callable[[float], None] | None = None) -> dict:
    """Verify the signed manifest before downloading any executable."""
    expected = _release_checksum(info)
    fd, filename = tempfile.mkstemp(prefix=".r3e-update-", suffix=".exe", dir=dest_dir)
    os.close(fd)
    target = Path(filename)
    try:
        _download_verified(info["assets"][EXE_NAME], EXE_NAME, expected, target, progress)
    except Exception:
        target.unlink(missing_ok=True)
        raise
    return {"exe": target, "sha256": expected}


def apply_update(new_exe: Path, expected: str) -> None:
    """Start a verified copy after download."""
    if not getattr(sys, "frozen", False):
        raise UpdateError("源码运行时不能自动替换，请用 git pull 或重新下载。")
    current = Path(sys.executable).resolve()
    helper_dir = None
    try:
        helper_dir = Path(tempfile.mkdtemp(prefix="r3e-update-"))
        helper = helper_dir / EXE_NAME
        shutil.copy2(new_exe, helper)
        with helper.open("rb") as handle:
            if hashlib.file_digest(handle, "sha256").hexdigest() != expected:
                raise UpdateError("下载的程序已变更，已取消更新。")
        subprocess.Popen([str(helper), "--update-helper", str(os.getpid()),
                          str(current), str(new_exe), expected],
                         cwd=str(current.parent), close_fds=True)
    except (OSError, UpdateError) as exc:
        if helper_dir:
            shutil.rmtree(helper_dir, ignore_errors=True)
        new_exe.unlink(missing_ok=True)
        raise UpdateError(f"无法启动更新程序：{exc}") from exc


def replace_update_file(current: Path, new_exe: Path, expected: str,
                        timeout: float = 120) -> None:
    """Stage and recheck an executable, then replace the installed file atomically."""
    fd, filename = tempfile.mkstemp(prefix=".r3e-replace-", suffix=".exe", dir=current.parent)
    os.close(fd)
    stage = Path(filename)
    try:
        shutil.copy2(new_exe, stage)
        with stage.open("rb") as handle:
            if hashlib.file_digest(handle, "sha256").hexdigest() != expected:
                raise UpdateError("下载的程序已变更，已取消更新。")
        deadline = time.monotonic() + timeout
        while True:
            try:
                stage.replace(current)
                break
            except PermissionError:
                if time.monotonic() >= deadline:
                    raise
                time.sleep(0.5)
    finally:
        stage.unlink(missing_ok=True)


def run_update_helper(args: list[str]) -> int:
    """等待原进程退出，然后替换文件并重新打开程序。"""
    import ctypes
    from ctypes import wintypes

    pid, current, new_exe, expected = args
    current = Path(current).resolve()
    new_exe = Path(new_exe).resolve()
    if new_exe.parent != current.parent:
        return 1
    legacy_csv = None
    if new_exe.name == LEGACY_EXE_DOWNLOAD:
        legacy_csv = current.with_name(LEGACY_CSV_DOWNLOAD)
        if not expected or Path(expected).resolve() != legacy_csv:
            return 1
    elif (not new_exe.name.startswith(".r3e-update-") or new_exe.suffix != ".exe"
          or not re.fullmatch(r"[0-9a-f]{64}", expected)):
        return 1
    kernel = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
    kernel.OpenProcess.restype = wintypes.HANDLE
    kernel.WaitForSingleObject.argtypes = [wintypes.HANDLE, wintypes.DWORD]
    kernel.WaitForSingleObject.restype = wintypes.DWORD
    kernel.CloseHandle.argtypes = [wintypes.HANDLE]
    verified_marker = None
    try:
        if legacy_csv is not None:
            # The legacy client has already checked both downloads against its release checksum list.
            # The EXE used for replacement must still match this running copy of the helper.
            with legacy_csv.open("rb") as handle:
                if handle.read(len(LEGACY_CSV_CONTENT) + 1) != LEGACY_CSV_CONTENT:
                    raise UpdateError("旧版更新兼容文件无效，请从发布页下载安装包。")
            verified_marker = legacy_csv
            with open(sys.executable, "rb") as handle:
                expected = hashlib.file_digest(handle, "sha256").hexdigest()
        handle = kernel.OpenProcess(0x00100000, False, int(pid))
        if handle:
            try:
                if kernel.WaitForSingleObject(handle, 120000) != 0:
                    raise UpdateError("等待旧程序退出超时。")
            finally:
                kernel.CloseHandle(handle)
        elif ctypes.get_last_error() != 87:  # ERROR_INVALID_PARAMETER: process exited
            raise ctypes.WinError(ctypes.get_last_error())
        replace_update_file(current, new_exe, expected)
        maintenance_errors = []
        import setup_tool

        try:
            setup_tool.register_installed_app(current)
        except OSError as exc:
            maintenance_errors.append(f"卸载入口登记失败：{exc}")
        try:
            desktop = setup_tool.desktop_shortcut_path()
            setup_tool.make_shortcut(desktop, current)
            for link in setup_tool.shortcut_paths():
                if link != desktop and link.is_file():
                    setup_tool.make_shortcut(link, current)
        except Exception as exc:
            maintenance_errors.append(f"创建快捷方式失败：{exc}")
        subprocess.Popen([str(current), "--cleanup-update-helper", str(Path(sys.executable).parent)],
                         cwd=str(current.parent), close_fds=True)
        if maintenance_errors:
            details = "\n".join(maintenance_errors)
            ctypes.windll.user32.MessageBoxW(
                None, f"程序已更新。\n{details}\n可以用安装包覆盖安装修复。",
                "R3E 汉化工具", 0x30)
        return 0
    except Exception as exc:
        ctypes.windll.user32.MessageBoxW(None, f"更新未完成：{exc}\n请关闭程序后重试，或下载安装包。", "R3E 汉化工具", 0x10)
        return 1
    finally:
        for path in (new_exe, verified_marker):
            if path is not None:
                try:
                    path.unlink(missing_ok=True)
                except OSError:
                    pass


def cleanup_helper(path: str) -> None:
    """只删除更新器创建的临时目录；帮助进程退出后重试。"""
    directory = Path(path).resolve()
    temp = Path(tempfile.gettempdir()).resolve()
    if directory.parent != temp or not directory.name.startswith("r3e-update-"):
        return
    for _ in range(20):
        try:
            shutil.rmtree(directory)
            return
        except FileNotFoundError:
            return
        except OSError:
            time.sleep(0.5)
