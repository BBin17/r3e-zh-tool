"""Create signed resources and finish a Windows release on the signing machine."""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
import zlib
from pathlib import Path

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from patch import read_translations
from translation_pack import MANIFEST_DOMAIN, PACK_HEADER, PACK_NAME, PUBLIC_KEY_NAME, parse_pack
from updater import (EXE_NAME, LEGACY_CSV_CONTENT, LEGACY_CSV_NAME, SETUP_NAME, SUMS_NAME,
                     SUMS_SIGNATURE_NAME, manifest_header)


def load_key(path: Path) -> Ed25519PrivateKey:
    key = serialization.load_pem_private_key(path.read_bytes(), None)
    if not isinstance(key, Ed25519PrivateKey):
        raise ValueError("发布私钥必须是 Ed25519 格式。")
    return key


def initialize_key(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    with os.fdopen(os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600), "wb") as handle:
        handle.write(Ed25519PrivateKey.generate().private_bytes(
            serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8, serialization.NoEncryption(),
        ))


def make_pack(key: Ed25519PrivateKey, source: Path, output: Path) -> None:
    with source.open(newline="", encoding="utf-8-sig") as handle:
        rows = csv.reader(handle)
        if next(rows, []) != ["key", "zh"] or any(len(row) != 2 for row in rows):
            raise ValueError("发布用 CSV 必须只包含 key,zh 两列。")
    translations = read_translations(source)
    payload = json.dumps(translations, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    data = PACK_HEADER + zlib.compress(payload, level=9)
    pack = data + key.sign(data)
    public_key = key.public_key().public_bytes_raw()
    parse_pack(pack, public_key)
    output.mkdir(parents=True, exist_ok=True)
    (output / PACK_NAME).write_bytes(pack)
    (output / PUBLIC_KEY_NAME).write_bytes(public_key)


def sign_manifest(key: Ed25519PrivateKey, folder: Path, version: str) -> None:
    from PyInstaller.archive.readers import CArchiveReader

    app = CArchiveReader(str(folder / EXE_NAME))
    setup = CArchiveReader(str(folder / SETUP_NAME))
    public_key = key.public_key().public_bytes_raw()
    if app.extract(PUBLIC_KEY_NAME) != public_key:
        raise ValueError("构建内置的公钥与签名私钥不一致。")
    if setup.extract(EXE_NAME) != (folder / EXE_NAME).read_bytes():
        raise ValueError("安装包内的程序与发布程序不一致。")
    parse_pack(app.extract(PACK_NAME), public_key)
    lines = [manifest_header(version)]
    legacy_csv = folder / LEGACY_CSV_NAME
    try:
        with legacy_csv.open("xb") as handle:
            handle.write(LEGACY_CSV_CONTENT)
    except FileExistsError:
        if legacy_csv.read_bytes() != LEGACY_CSV_CONTENT:
            raise ValueError("发布目录已有同名 CSV。请使用干净目录签名，避免发布明文译文。") from None
    for name in (EXE_NAME, SETUP_NAME, LEGACY_CSV_NAME):
        with (folder / name).open("rb") as handle:
            digest = hashlib.file_digest(handle, "sha256").hexdigest()
        lines.append(f"{digest}  {name}\n")
    manifest = "".join(lines).encode("ascii")
    (folder / SUMS_NAME).write_bytes(manifest)
    (folder / SUMS_SIGNATURE_NAME).write_bytes(key.sign(MANIFEST_DOMAIN + manifest))


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--key", type=Path, required=True, help="签名电脑上的私钥路径")
    commands = parser.add_subparsers(dest="action", required=True)
    commands.add_parser("init-key", help="一次性生成发布私钥")
    pack = commands.add_parser("pack", help="生成签名译文包及公钥，供 Windows 构建")
    pack.add_argument("source", type=Path)
    pack.add_argument("output", type=Path)
    manifest = commands.add_parser("manifest", help="给已构建的 Windows 文件签名")
    manifest.add_argument("folder", type=Path)
    manifest.add_argument("version", help="完整发布标签，例如 v0.3.28")
    args = parser.parse_args()
    if args.action == "init-key":
        initialize_key(args.key)
        return
    key = load_key(args.key)
    if args.action == "pack":
        make_pack(key, args.source, args.output)
    else:
        sign_manifest(key, args.folder, args.version)


if __name__ == "__main__":
    main()
