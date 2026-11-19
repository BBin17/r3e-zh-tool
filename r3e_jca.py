"""RaceRoom .jca 容器 + Localization 表读写核心库.

容器格式（Race WTCC / SimBin, 版本 2）:
    u32  0xFFFFB10F  magic
    u32  version     (2 => 未压缩)
    u32  data_size   解密后的字节数
    u32  zlen        压缩后字节数（0 表示未压缩）
    body             Blowfish-ECB 加密（每 8 字节一组，按 x86 小端解释）

解密: body -> Blowfish 解密 -> (若 zlen 则 zlib 解压) -> 每字节 XOR 0xEB
加密: 明文 -> XOR 0xEB -> (压缩) -> 补齐到 8 的倍数 -> Blowfish 加密

Localization.jca 解密后的结构:
    [0, table_start)                     一段“序言”字节（原样保留）
    [table_start, EOF)                   连续的记录:
                                         u32 字符数 n + n*2 字节 UTF-16LE
                                         记录成对出现: $key, value
    文件内共 5 段语言区，顺序为 de_DE, en_GB, es_ES, fr_FR, it_IT，
    每段以 $Menu_Breadcrumb_Navigation 开头。
"""
from __future__ import annotations

import json
import struct
import sys
import zlib
from dataclasses import dataclass
from pathlib import Path

MAGIC = 0xFFFFB10F
RACEROOM_KEY = bytes([
    0x5F, 0x67, 0xB3, 0x37, 0xA2, 0x76, 0x9A, 0x34,
    0x13, 0xAC, 0x28, 0xD0, 0x92, 0x6E, 0x32, 0x90,
    0xF7, 0x55, 0xFE, 0x4A,
])
SECTION_ORDER = ["de_DE", "en_GB", "es_ES", "fr_FR", "it_IT"]
ANCHOR = "$Menu_Breadcrumb_Navigation"
# 用 $YourCurrentLevel 的译文识别每一段属于哪种语言
LANG_FINGERPRINTS = {
    "Dein aktuelles Level": "de_DE",
    "Your current level": "en_GB",
    "Tu nivel actual": "es_ES",
    "Votre niveau actuel": "fr_FR",
    "Il tuo livello attuale": "it_IT",
}

def _resource(name: str) -> Path:
    """打包成 exe 后资源在 _MEIPASS，源码运行时在脚本目录。"""
    base = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent))
    return base / name


TABLES_PATH = _resource("blowfish_tables.json")


class Blowfish:
    def __init__(self, key: bytes, tables):
        self.P = list(tables["p"])
        # .jca 版本 2 使用第 1 号自定义 S 盒（1024 个 32 位字，拆成 S[4][256]）
        flat = tables["sbox"][1]
        self.S = [list(flat[i * 256:(i + 1) * 256]) for i in range(4)]
        j = 0
        for i in range(18):
            data = 0
            for _ in range(4):
                data = ((data << 8) | key[j]) & 0xFFFFFFFF
                j += 1
                if j >= len(key):
                    j = 0
            self.P[i] ^= data
        l = r = 0
        for i in range(0, 18, 2):
            l, r = self.encipher(l, r)
            self.P[i], self.P[i + 1] = l, r
        for i in range(4):
            for j in range(0, 256, 2):
                l, r = self.encipher(l, r)
                self.S[i][j], self.S[i][j + 1] = l, r

    def _f(self, x: int) -> int:
        return ((((self.S[0][x >> 24] + self.S[1][(x >> 16) & 0xFF]) & 0xFFFFFFFF)
                 ^ self.S[2][(x >> 8) & 0xFF]) + self.S[3][x & 0xFF]) & 0xFFFFFFFF

    def encipher(self, l: int, r: int):
        P = self.P
        for i in range(16):
            l ^= P[i]
            r ^= self._f(l)
            l, r = r, l
        l, r = r, l
        r ^= P[16]
        l ^= P[17]
        return l, r

    def decipher(self, l: int, r: int):
        P = self.P
        for i in range(17, 1, -1):
            l ^= P[i]
            r ^= self._f(l)
            l, r = r, l
        l, r = r, l
        r ^= P[1]
        l ^= P[0]
        return l, r

    def _run(self, data: bytes, fn, progress=None) -> bytes:
        out = bytearray(len(data))
        total = len(data) // 8
        for i, off in enumerate(range(0, len(data), 8)):
            l, r = struct.unpack_from("<II", data, off)
            l, r = fn(l, r)
            struct.pack_into("<II", out, off, l, r)
            if progress and (i & 0x3FFF) == 0:
                progress(i, total)
        if progress:
            progress(total, total)
        return bytes(out)

    def decrypt(self, data: bytes, progress=None) -> bytes:
        return self._run(data, self.decipher, progress)

    def encrypt(self, data: bytes, progress=None) -> bytes:
        return self._run(data, self.encipher, progress)


_bf_cache = None


def blowfish() -> Blowfish:
    global _bf_cache
    if _bf_cache is None:
        _bf_cache = Blowfish(RACEROOM_KEY, json.loads(TABLES_PATH.read_text(encoding="utf-8")))
    return _bf_cache


@dataclass
class JcaFile:
    version: int
    plain: bytes

    @classmethod
    def load(cls, path: str | Path, progress=None) -> "JcaFile":
        return cls.from_bytes(Path(path).read_bytes(), progress)

    @classmethod
    def from_bytes(cls, blob: bytes, progress=None) -> "JcaFile":
        if len(blob) < 16 or (len(blob) - 16) % 8:
            raise ValueError("JCA 文件不完整或加密数据未对齐。")
        magic, version, usize, zlen = struct.unpack_from("<IIII", blob, 0)
        if magic != MAGIC:
            raise ValueError("不是 .jca 文件（magic 不匹配）")
        body = blowfish().decrypt(blob[16:], progress)
        if zlen:
            body = zlib.decompress(body[:zlen])
        plain = bytes(b ^ 0xEB for b in body[:usize])
        return cls(version, plain)

    def dump(self, path: str | Path, progress=None) -> None:
        data = bytes(b ^ 0xEB for b in self.plain)
        if len(data) % 8:
            data += b"\x00" * (8 - len(data) % 8)
        header = struct.pack("<IIII", MAGIC, self.version, len(self.plain), 0)
        Path(path).write_bytes(header + blowfish().encrypt(data, progress))


def parse_records(plain: bytes, start: int) -> list[str]:
    """从 start 开始逐条读取 u32 长度 + UTF-16LE 字符串，直到文件尾。"""
    recs, off = [], start
    while off + 4 <= len(plain):
        n = struct.unpack_from("<I", plain, off)[0]
        recs.append(plain[off + 4:off + 4 + n * 2].decode("utf-16-le"))
        off += 4 + n * 2
    if off != len(plain):
        raise ValueError(f"记录解析未对齐：结束于 {off}，文件长 {len(plain)}")
    return recs


def find_table_start(plain: bytes) -> int:
    """找出真正的表起点；起点之前是原样保留的序言字节。"""
    needle = ANCHOR.encode("utf-16-le")
    pos = plain.find(needle, 4)
    while pos != -1:
        start = pos - 4
        if start >= 0 and struct.unpack_from("<I", plain, start)[0] * 2 + 4 == len(needle) + 4:
            try:
                parse_records(plain, start)
                return start
            except ValueError:
                pass
        pos = plain.find(needle, pos + 1)
    raise ValueError("找不到 Localization 表起点")


@dataclass
class Section:
    lang: str
    pairs: list[tuple[str, str]]  # (key, value)


@dataclass
class Localization:
    prologue: bytes
    sections: list[Section]

    @classmethod
    def load(cls, jca: JcaFile) -> "Localization":
        start = find_table_start(jca.plain)
        recs = parse_records(jca.plain, start)
        anchors = [i for i, s in enumerate(recs) if s == ANCHOR]
        if len(anchors) != 5:
            raise ValueError(f"语言段数量异常: {len(anchors)}")
        sections = []
        bounds = anchors + [len(recs)]
        for i in range(5):
            chunk = recs[bounds[i]:bounds[i + 1]]
            pairs = [(chunk[k], chunk[k + 1]) for k in range(0, len(chunk) - 1, 2)]
            lang = SECTION_ORDER[i]
            for k, v in pairs:
                if k == "$YourCurrentLevel" and v in LANG_FINGERPRINTS:
                    lang = LANG_FINGERPRINTS[v]
                    break
            sections.append(Section(lang, pairs))
        return cls(jca.plain[:start], sections)

    def section(self, lang: str) -> Section:
        for s in self.sections:
            if s.lang == lang:
                return s
        raise KeyError(lang)

    def rebuild(self) -> bytes:
        out = bytearray(self.prologue)
        for sec in self.sections:
            for k, v in sec.pairs:
                for text in (k, v):
                    raw = text.encode("utf-16-le")
                    out += struct.pack("<I", len(raw) // 2) + raw
        return bytes(out)
