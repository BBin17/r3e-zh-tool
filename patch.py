"""把翻译写回 Localization.jca，生成可直接替换到游戏目录的补丁文件。

用法:
    python -I patch.py original.jca translations.csv out.jca --target en_GB

translations.csv 支持两种列布局:
    key,zh
    key,source,zh           （extract.py 导出的格式）
空白的 zh 视为未翻译，保留原文。
"""
import argparse
import csv
import struct
import sys
from pathlib import Path

if __name__ == "__main__":
    sys.path.insert(0, str(Path(__file__).parent))
from r3e_jca import JcaFile, Localization  # noqa: E402


def read_translations(path: str | Path) -> dict[str, str]:
    with open(path, newline="", encoding="utf-8-sig") as fh:
        return parse_translations(fh)


def parse_translations(lines) -> dict[str, str]:
    rows = csv.reader(lines)
    header = [column.strip().lower() for column in next(rows, [])]
    if "key" not in header:
        raise ValueError("CSV 缺少 key 列。")
    translation_column = "zh" if "zh" in header else "target"
    if translation_column not in header:
        raise ValueError("CSV 缺少 zh 或 target 译文列。")
    key_index = header.index("key")
    translation_index = header.index(translation_column)
    result: dict[str, str] = {}
    for row in rows:
        if len(row) <= max(key_index, translation_index):
            continue
        key, value = row[key_index].strip(), row[translation_index]
        if key and value.strip():
            result[key] = value
    return result


def apply_translations(sections, translations: dict[str, str]) -> tuple[set[str], int]:
    matched = set()
    applied = 0
    for section in sections:
        for i, (key, value) in enumerate(section.pairs):
            if key in translations:
                matched.add(key)
                if translations[key] != value:
                    section.pairs[i] = (key, translations[key])
                    applied += 1
    return matched, applied


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("jca", help="原版 Localization.jca")
    ap.add_argument("translations", help="翻译 CSV")
    ap.add_argument("out", help="输出补丁文件路径")
    ap.add_argument("--target", default="en_GB",
                    help="替换哪个语言段（默认 en_GB）；可用逗号指定多个，如 en_GB,de_DE,it_IT")
    args = ap.parse_args()

    targets = [t.strip() for t in args.target.split(",") if t.strip()]
    translations = read_translations(args.translations)
    jca = JcaFile.load(args.jca)
    loc = Localization.load(jca)
    original = [list(s.pairs) for s in loc.sections]

    seen, applied = set(), 0
    for target in targets:
        sec = loc.section(target)
        for i, (key, value) in enumerate(sec.pairs):
            if key in translations:
                seen.add(key)
                sec.pairs[i] = (key, translations[key])
                applied += 1

    missing = [k for k in translations if k not in seen]
    new_plain = loc.rebuild()
    JcaFile(jca.version, new_plain).dump(args.out)

    # 自校验：重新读回补丁，确认只有目标段的对应条目发生变化
    check = Localization.load(JcaFile.load(args.out))
    assert check.prologue == loc.prologue, "序言字节不一致"
    changed = 0
    for old_pairs, new_sec in zip(original, check.sections):
        assert len(old_pairs) == len(new_sec.pairs), "记录数不一致"
        for (k1, v1), (k2, v2) in zip(old_pairs, new_sec.pairs):
            assert k1 == k2, "键顺序不一致"
            if v1 != v2:
                assert new_sec.lang in targets, f"{new_sec.lang} 段被意外修改"
                changed += 1

    print(f"已写入 {args.out}")
    print(f"  替换条目: {applied}（实际变化: {changed}）")
    print(f"  文件大小: {Path(args.out).stat().st_size} 字节（原 {Path(args.jca).stat().st_size}）")
    if missing:
        print(f"  未匹配到的键: {len(missing)}")
        for k in missing[:10]:
            print(f"    {k}")


if __name__ == "__main__":
    main()
