"""Read the signed, compressed base translation resource."""
from __future__ import annotations

import json
import sys
import zlib
from pathlib import Path

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey

PACK_NAME = "zh-translations.r3ezh"
PUBLIC_KEY_NAME = "release-signing.pub"
PACK_HEADER = b"R3E-ZH\x01"
SIGNATURE_SIZE = 64
MANIFEST_DOMAIN = b"R3E release manifest\x00"
MAX_TRANSLATION_BYTES = 16 * 1024 * 1024


def bundled_path(name: str) -> Path:
    base = getattr(sys, "_MEIPASS", None)
    return (Path(base) if base else Path(__file__).resolve().parent / "release") / name


def verify_signature(message: bytes, signature: bytes, public_key: bytes | None = None) -> None:
    try:
        key = bundled_path(PUBLIC_KEY_NAME).read_bytes() if public_key is None else public_key
        Ed25519PublicKey.from_public_bytes(key).verify(signature, message)
    except (InvalidSignature, ValueError, OSError) as exc:
        raise ValueError("发布签名验证失败。请从项目的 GitHub 发布页重新获取文件。") from exc


def parse_pack(data: bytes, public_key: bytes | None = None) -> dict[str, str]:
    if not data.startswith(PACK_HEADER) or len(data) <= len(PACK_HEADER) + SIGNATURE_SIZE:
        raise ValueError("译文包格式无效。")
    message, signature = data[:-SIGNATURE_SIZE], data[-SIGNATURE_SIZE:]
    verify_signature(message, signature, public_key)
    try:
        decoder = zlib.decompressobj()
        payload = decoder.decompress(message[len(PACK_HEADER):], MAX_TRANSLATION_BYTES + 1)
        if len(payload) > MAX_TRANSLATION_BYTES or not decoder.eof or decoder.unused_data:
            raise ValueError("译文数据长度无效。")
        translations = json.loads(payload)
    except (ValueError, zlib.error) as exc:
        raise ValueError("译文包内容无效。") from exc
    if not isinstance(translations, dict) or not translations or any(
        not key or not isinstance(value, str) or not value.strip() for key, value in translations.items()
    ):
        raise ValueError("译文包里没有有效译文。")
    return translations
