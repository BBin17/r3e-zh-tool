"""从完整工作表生成发布用译文表 zh-translations.csv。

只保留 key 和 zh 两列，不含英文原文（游戏原文不随程序公开发布）。
与原文相同的译文（专有名词、网址等）也不输出，它们在游戏里保持原样。

用法：python make_publish_csv.py [输出路径]
"""
import csv
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
SOURCE = HERE / "R3E-Localization-zh.csv"


def main() -> None:
    out = Path(sys.argv[1]) if len(sys.argv) > 1 else HERE / "release" / "zh-translations.csv"
    out.parent.mkdir(parents=True, exist_ok=True)
    kept = skipped_same = skipped_empty = 0
    with open(SOURCE, newline="", encoding="utf-8-sig") as src, \
            open(out, "w", newline="", encoding="utf-8") as dst:
        writer = csv.writer(dst)
        writer.writerow(["key", "zh"])
        for row in csv.DictReader(src):
            key = (row.get("key") or "").strip()
            zh = (row.get("zh") or "").strip()
            source = (row.get("source") or "").strip()
            if not key or not zh:
                skipped_empty += 1
                continue
            if zh == source:
                skipped_same += 1
                continue
            writer.writerow([key, zh])
            kept += 1
    print(f"写出 {out}：{kept} 条；跳过与原文相同 {skipped_same} 条，空译文 {skipped_empty} 条")


if __name__ == "__main__":
    main()
