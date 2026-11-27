"""R3E 汉化工具 · 安装程序

安装到 %LOCALAPPDATA%\\Programs\\R3E-ZH-Tool，并创建开始菜单和桌面快捷方式。
程序本体和译文表都已打包在安装程序里，安装不需要联网。
之后程序内的“检查更新”会从 GitHub Releases 下载新版本。

用法：
  R3E-ZH-Tool-Setup.exe               安装（已安装则覆盖）
  R3E-ZH-Tool-Setup.exe --uninstall   恢复游戏原版后卸载
"""
from __future__ import annotations

import ctypes
import hashlib
import os
import shutil
import subprocess
import sys
import tempfile
import tkinter as tk
from pathlib import Path
from tkinter import messagebox

APP_NAME = "R3E 汉化工具"
APP_VERSION = "0.3.35"
DEVELOPER = "BBin17"
EXE_NAME = "R3E-ZH-Tool.exe"
SHORTCUT_NAME = "R3E 汉化工具.lnk"
LOCAL_BUILD_MARKER = "r3e_local_features.flag"
UNINSTALL_SCRIPT = "uninstall.ps1"
UNINSTALL_EXE = "R3E-ZH-Tool-Uninstall.exe"
UNINSTALL_ROOT = r"Software\Microsoft\Windows\CurrentVersion\Uninstall"

# Run a temporary copy so Windows can remove the installed executable.
UNINSTALL_LAUNCHER = rf"""$ErrorActionPreference = 'Stop'
$temp = Join-Path ([IO.Path]::GetTempPath()) ('r3e-uninstall-' + [guid]::NewGuid())
try {{
    New-Item -Path $temp -ItemType Directory | Out-Null
    $exe = Join-Path $temp '{UNINSTALL_EXE}'
    Copy-Item -LiteralPath (Join-Path $PSScriptRoot '{EXE_NAME}') -Destination $exe
    [IO.Directory]::SetCurrentDirectory([IO.Path]::GetTempPath())
    $process = Start-Process -FilePath $exe -ArgumentList '--uninstall-installed' -WorkingDirectory $temp -Wait -PassThru
    exit $process.ExitCode
}} catch {{
    Add-Type -AssemblyName System.Windows.Forms
    [Windows.Forms.MessageBox]::Show("无法启动卸载程序。`n$_", '{APP_NAME}') | Out-Null
    exit 1
}} finally {{
    if (Test-Path -LiteralPath $temp) {{
        Remove-Item -LiteralPath $temp -Recurse -Force
    }}
}}
"""


def local_build() -> bool:
    return getattr(sys, "frozen", False) and (Path(sys._MEIPASS) / LOCAL_BUILD_MARKER).is_file()


def shortcut_name() -> str:
    return "R3E 汉化工具（本地测试）.lnk" if local_build() else SHORTCUT_NAME


def payload_dir() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys._MEIPASS)  # type: ignore[attr-defined]
    return Path(__file__).resolve().parent / "release"


def install_dir() -> Path:
    base = Path(os.environ.get("LOCALAPPDATA") or Path.home() / "AppData" / "Local")
    name = "R3E-ZH-Tool-Local" if local_build() else "R3E-ZH-Tool"
    return base / "Programs" / name


def desktop_shortcut_path() -> Path:
    # Windows 用户可能把桌面重定向到 OneDrive 或其他目录。
    buffer = ctypes.create_unicode_buffer(32768)
    result = ctypes.windll.shell32.SHGetFolderPathW(None, 0x10, None, 0, buffer)
    if result != 0:
        raise OSError(f"无法找到桌面目录（错误代码 {result}）")
    return Path(buffer.value) / shortcut_name()


def shortcut_paths() -> list[Path]:
    appdata = Path(os.environ.get("APPDATA") or Path.home() / "AppData" / "Roaming")
    start = appdata / "Microsoft" / "Windows" / "Start Menu" / "Programs"
    return [start / shortcut_name(), desktop_shortcut_path()]


def uninstall_key() -> str:
    return f"{UNINSTALL_ROOT}\\{install_dir().name}"


def register_installed_app(exe: Path) -> None:
    if exe.resolve() != (install_dir() / EXE_NAME).resolve():
        return
    import winreg

    script = exe.with_name(UNINSTALL_SCRIPT)
    fd, path = tempfile.mkstemp(prefix=".uninstall-", dir=exe.parent)
    temp = Path(path)
    try:
        with os.fdopen(fd, "w", encoding="utf-8-sig") as handle:
            handle.write(UNINSTALL_LAUNCHER)
        temp.replace(script)
    finally:
        temp.unlink(missing_ok=True)

    powershell = Path(os.environ["SystemRoot"]) / "System32" / "WindowsPowerShell" / "v1.0" / "powershell.exe"
    command = f'"{powershell}" -NoProfile -NonInteractive -WindowStyle Hidden -ExecutionPolicy Bypass -File "{script}"'
    name = Path(shortcut_name()).stem
    with winreg.CreateKeyEx(winreg.HKEY_CURRENT_USER, uninstall_key(), access=winreg.KEY_SET_VALUE) as key:
        for field, value in {
            "DisplayVersion": APP_VERSION,
            "Publisher": DEVELOPER,
            "DisplayIcon": f'"{exe}",0',
            "InstallLocation": str(exe.parent),
            "UninstallString": command,
        }.items():
            winreg.SetValueEx(key, field, 0, winreg.REG_SZ, value)
        for field in ("NoModify", "NoRepair"):
            winreg.SetValueEx(key, field, 0, winreg.REG_DWORD, 1)
        winreg.SetValueEx(key, "DisplayName", 0, winreg.REG_SZ, name)


def _powershell(script: str) -> None:
    # 写成带 BOM 的 .ps1 再执行，避免中文路径在命令行参数里被破坏
    fd, name = tempfile.mkstemp(suffix=".ps1")
    try:
        with os.fdopen(fd, "w", encoding="utf-8-sig") as fh:
            fh.write(script)
        proc = subprocess.run(
            ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", name],
            capture_output=True, text=True, encoding="utf-8", errors="replace",
            creationflags=0x08000000)  # CREATE_NO_WINDOW
    finally:
        os.unlink(name)
    if proc.returncode != 0:
        raise RuntimeError(f"创建快捷方式失败：{(proc.stderr or proc.stdout).strip()[:300]}")


def _shortcut_icon(target: Path) -> Path:
    source = (payload_dir() if getattr(sys, "frozen", False) else Path(__file__).parent) / "app.ico"
    if not source.is_file():
        return target
    data = source.read_bytes()
    digest = hashlib.sha256(data).hexdigest()[:12]
    icon = target.parent / f"r3e-icon-{digest}.ico"
    if icon.is_file() and icon.read_bytes() == data:
        return icon
    fd, name = tempfile.mkstemp(prefix=".r3e-icon-", dir=target.parent)
    temp = Path(name)
    try:
        with os.fdopen(fd, "wb") as handle:
            handle.write(data)
        temp.replace(icon)
    finally:
        temp.unlink(missing_ok=True)
    return icon


def make_shortcut(link: Path, target: Path) -> None:
    link.parent.mkdir(parents=True, exist_ok=True)
    # PowerShell 单引号字符串用两个单引号表示路径中的单引号。
    link_str = str(link).replace("'", "''")
    target_str = str(target).replace("'", "''")
    working_dir = str(target.parent).replace("'", "''")
    icon_str = str(_shortcut_icon(target)).replace("'", "''")
    script = (
        "$ErrorActionPreference = 'Stop'; "
        "$s = (New-Object -ComObject WScript.Shell).CreateShortcut("
        f"'{link_str}'); "
        f"$s.TargetPath = '{target_str}'; "
        f"$s.WorkingDirectory = '{working_dir}'; "
        f"$s.IconLocation = '{icon_str},0'; "
        "$s.Save()"
    )
    _powershell(script)
    notify = ctypes.windll.shell32.SHChangeNotify
    notify.argtypes = (ctypes.c_long, ctypes.c_uint, ctypes.c_wchar_p, ctypes.c_wchar_p)
    notify.restype = None
    notify(0x2000, 0x1005, str(link), None)  # SHCNE_UPDATEITEM; path and flush


def install() -> Path:
    src = payload_dir()
    dst = install_dir()
    dst.mkdir(parents=True, exist_ok=True)
    exe = dst / EXE_NAME
    fd, name = tempfile.mkstemp(prefix=".r3e-install-", dir=dst)
    os.close(fd)
    stage = Path(name)
    try:
        shutil.copy2(src / EXE_NAME, stage)
        stage.replace(exe)
    finally:
        stage.unlink(missing_ok=True)
    for link in shortcut_paths():
        make_shortcut(link, exe)
    register_installed_app(exe)
    return exe


def uninstall() -> None:
    import winreg

    links = shortcut_paths()
    dst = install_dir()
    try:
        (dst / EXE_NAME).unlink(missing_ok=True)
    except PermissionError as exc:
        raise RuntimeError("请先退出正在运行的 R3E 汉化工具，再重试卸载。") from exc
    if dst.exists():
        shutil.rmtree(dst)
    for link in links:
        link.unlink(missing_ok=True)
    try:
        winreg.DeleteKey(winreg.HKEY_CURRENT_USER, uninstall_key())
    except FileNotFoundError:
        pass


def tool_running() -> bool:
    tasks = subprocess.run(
        ["tasklist", "/FI", f"IMAGENAME eq {EXE_NAME}", "/FO", "CSV", "/NH"],
        capture_output=True, text=True, errors="replace", check=True, timeout=15,
        creationflags=0x08000000,
    )
    return f'"{EXE_NAME}"'.casefold() in tasks.stdout.casefold()


def uninstall_interactive(restore_original, *, parent) -> int:
    if not messagebox.askyesno(
        APP_NAME, "卸载前会先自动恢复 RaceRoom 原版。\n请退出游戏和汉化工具后继续。\n\n现在恢复并卸载吗？",
        parent=parent,
    ):
        return 0
    try:
        restore_original()
    except Exception as exc:
        messagebox.showerror(APP_NAME, f"未达到卸载条件，工具已保留。\n\n{exc}", parent=parent)
        return 1
    try:
        uninstall()
    except (OSError, RuntimeError) as exc:
        messagebox.showerror(APP_NAME, f"卸载失败：{exc}", parent=parent)
        return 1
    messagebox.showinfo(APP_NAME, "原版检查和恢复已完成，汉化工具已卸载。", parent=parent)
    return 0


def uninstall_from_setup() -> int:
    # Use the bundled app and the same restore path as Control Panel.
    with tempfile.TemporaryDirectory(prefix="r3e-uninstall-") as directory:
        helper = Path(directory) / UNINSTALL_EXE
        shutil.copy2(payload_dir() / EXE_NAME, helper)
        return subprocess.call([str(helper), "--uninstall-installed"], cwd=directory,
                               env={**os.environ, "PYINSTALLER_RESET_ENVIRONMENT": "1"})


def main() -> None:
    root = tk.Tk()
    root.withdraw()
    try:
        if "--uninstall" in sys.argv:
            raise SystemExit(uninstall_from_setup())
        target = install_dir()
        title = f"{APP_NAME} · 本地测试" if local_build() else APP_NAME
        if not messagebox.askyesno(title, f"安装到:\n{target}\n\n继续吗？"):
            return
        exe = install()
        if messagebox.askyesno(APP_NAME, "安装完成。现在启动吗？"):
            subprocess.Popen([str(exe)], cwd=str(exe.parent))
    except Exception as exc:  # noqa: BLE001
        messagebox.showerror(APP_NAME, f"安装失败：{exc}")
    finally:
        root.destroy()


if __name__ == "__main__":
    main()
