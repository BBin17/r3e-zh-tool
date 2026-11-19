"""Build the Windows app and installer from a signed translation resource."""
import argparse
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

from setup_tool import LOCAL_BUILD_MARKER
from translation_pack import PACK_NAME, PUBLIC_KEY_NAME, parse_pack
from updater import EXE_NAME, SETUP_NAME

ROOT = Path(__file__).resolve().parent
LOCAL_SETUP_NAME = "R3E-ZH-Tool-Local-Setup.exe"
NATIVE_MODULES = ("r3e_jca", "patch", "translation_pack")
MENU_FILES = ("home-zh.js", "home-zh.json", "section-zh.json", "achievements-zh.json",
              "toolbar-zh.json", "legacy-zh.json", "car-setup-zh.json", "drive-zh.json", "ranked-zh.json")


def stage_code(source: Path) -> None:
    """Keep selected modules available to the freezer only as native extensions."""
    source.mkdir()
    for name in ("app", "setup_tool", "updater", "extra_ui", "steam_depot", *NATIVE_MODULES):
        shutil.copy2(ROOT / f"{name}.py", source)
    for name in ("rr_menu", "rr_hud"):
        package = source / name
        package.mkdir()
        for module in (ROOT / name).glob("*.py"):
            shutil.copy2(module, package)

    subprocess.run([sys.executable, "-m", "Cython.Build.Cythonize", "-3", "-i",
                    *(f"{name}.py" for name in NATIVE_MODULES)], cwd=source, check=True)
    for name in NATIVE_MODULES:
        if not list(source.glob(f"{name}.*.pyd")):
            raise RuntimeError(f"未生成 Windows 扩展：{name}")
        (source / f"{name}.py").unlink()


def build_exe(script: Path, filename: str, output: Path, resources: list[Path],
              extra_args: list[str] | None = None) -> None:
    command = [sys.executable, "-m", "PyInstaller", "--noconfirm", "--clean", "--onefile",
               "--noconsole", "--name", Path(filename).stem, "--icon", str(ROOT / "app.ico"),
               "--distpath", str(output), "--workpath", str(output / "build"),
               "--specpath", str(output)]
    for resource in resources:
        command.extend(["--add-data", f"{resource};."])
    subprocess.run([*command, *(extra_args or []), str(script)], cwd=script.parent, check=True)


def app_build_args() -> list[str]:
    menu = ROOT / "rr_menu" / "assets"
    flags = ["--copy-metadata", "fonttools", "--copy-metadata", "websocket-client",
             "--hidden-import", "csv", "--hidden-import", "cryptography.hazmat.primitives.asymmetric.ed25519"]
    for name in MENU_FILES:
        path = menu / name
        if not path.is_file():
            raise FileNotFoundError(f"缺少发布用菜单资源：{path}")
        flags.extend(["--add-data", f"{path};rr_menu/assets"])
    flags.extend(["--add-data", f"{ROOT / 'docs/images/donate'};docs/images/donate"])
    return flags


def verify_native_payload(exe: Path) -> None:
    from PyInstaller.archive.readers import CArchiveReader

    archive = CArchiveReader(str(exe))
    python_modules = archive.open_embedded_archive("PYZ.pyz").toc
    for name in NATIVE_MODULES:
        if name in python_modules or not any(
            entry.startswith(f"{name}.") and entry.endswith(".pyd") for entry in archive.toc
        ):
            raise RuntimeError(f"发布程序中未使用 Windows 原生模块：{name}")
    if any(entry.lower().endswith(".csv") for entry in archive.toc):
        raise RuntimeError("发布程序中包含明文 CSV。")


def copy_build_output(source: Path, target: Path) -> None:
    # New files inherit the output folder's ACL. Moving from the private
    # TemporaryDirectory would carry its restricted ACL into the output.
    fd, name = tempfile.mkstemp(prefix=".r3e-built-", dir=target.parent)
    try:
        with os.fdopen(fd, "wb") as handle, source.open("rb") as binary:
            shutil.copyfileobj(binary, handle)
        Path(name).replace(target)
    finally:
        Path(name).unlink(missing_ok=True)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--resources", type=Path, default=ROOT / "release",
                        help="包含签名译文包与发布公钥的目录")
    parser.add_argument("--output", type=Path)
    parser.add_argument("--local-test", "--local-extras", dest="local_extras", action="store_true",
                        help="构建使用独立安装目录、可手动检查更新的本地测试版")
    args = parser.parse_args()
    if sys.platform != "win32":
        parser.error("请在 Windows 上使用带 C++ 构建工具的 Python 构建。")
    output = (args.output or ROOT / "dist" / ("local-test" if args.local_extras else "release")).resolve()
    if args.local_extras and output == (ROOT / "dist" / "release").resolve():
        parser.error("本地测试版需要单独的输出目录。")
    resources = args.resources.resolve()
    pack, public_key = resources / PACK_NAME, resources / PUBLIC_KEY_NAME
    if not pack.is_file() or not public_key.is_file():
        parser.error("缺少签名译文包或公钥。请先使用 release_signing.py pack 生成。")
    parse_pack(pack.read_bytes(), public_key.read_bytes())
    output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="r3e-build-", dir=output.parent) as folder:
        stage = Path(folder)
        source = stage / "source"
        stage_code(source)
        branding = []
        setup_name = SETUP_NAME
        if args.local_extras:
            marker = stage / LOCAL_BUILD_MARKER
            marker.write_text("local test\n", encoding="ascii")
            branding.append(marker)
            setup_name = LOCAL_SETUP_NAME
        build_exe(source / "app.py", EXE_NAME, stage,
                  [ROOT / "blowfish_tables.json", ROOT / "app.ico", ROOT / "app-icon-preview.png",
                   pack, public_key, *branding], app_build_args())
        verify_native_payload(stage / EXE_NAME)
        build_exe(source / "setup_tool.py", setup_name, stage, [stage / EXE_NAME, ROOT / "app.ico", *branding])
        output.mkdir(parents=True, exist_ok=True)
        for name in (EXE_NAME, setup_name):
            copy_build_output(stage / name, output / name)
    print(f"Windows 构建已完成：{output}")


if __name__ == "__main__":
    main()
