"""从 RaceRoom 的 Localization.jca 导出翻译工作表（CSV）。

用法:
    python -I extract.py "D:\\...\\Game\\GameData\\General\\Localization.jca" out.csv
    python -I extract.py "D:\\...\\Localization.jca" out.csv --all
"""
import argparse
import csv
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from r3e_jca import JcaFile, Localization  # noqa: E402


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("jca", help="Localization.jca 路径（只读，不会修改）")
    ap.add_argument("out", help="输出 CSV 路径")
    ap.add_argument("--all", action="store_true", help="同时导出全部 5 种语言的原文")
    ap.add_argument("--source-lang", default="en_GB", help="作为译出语的语言段")
    args = ap.parse_args()

    loc = Localization.load(JcaFile.load(args.jca))
    src = loc.section(args.source_lang)
    langs = [s.lang for s in loc.sections]

    with open(args.out, "w", newline="", encoding="utf-8-sig") as fh:
        w = csv.writer(fh)
        header = ["key", "source", "zh", "status"]
        if args.all:
            header += [f"raw_{l}" for l in langs]
        w.writerow(header)
        for key, value in src.pairs:
            row = [key, value, "", "todo"]
            if args.all:
                others = {s.lang: dict(s.pairs).get(key, "") for s in loc.sections}
                row += [others[l] for l in langs]
            w.writerow(row)

    print(f"已导出 {len(src.pairs)} 条 {args.source_lang} 字符串 -> {args.out}")
    print(f"语言段: {', '.join(langs)}")


if __name__ == "__main__":
    main()
