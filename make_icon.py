"""原创 app 图标：维修站呼叫牌与方格终点旗。

奶油白对话牌代表语言内容，红/白方格旗代表赛车；红色重点行是已转换的文本。
使用工具本身的石墨、暖白、RaceRoom 红配色，不使用游戏商标或现成字体。

用法：python make_icon.py    # 输出 app.ico 和 app-icon-preview.png
依赖：Pillow。
"""
from pathlib import Path

from PIL import Image, ImageDraw

HERE = Path(__file__).resolve().parent
OUT = HERE / "app.ico"
PREVIEW = HERE / "app-icon-preview.png"
SIZE = 1024
INK = (22, 24, 28, 255)
PANEL = (34, 39, 45, 255)
PAPER = (243, 240, 233, 255)
RED = (208, 2, 27, 255)


def _checker(draw: ImageDraw.ImageDraw, box, cell: int) -> None:
    x0, y0, x1, y1 = box
    rows = (y1-y0) // cell
    cols = (x1-x0) // cell
    for row in range(rows):
        for col in range(cols):
            color = PAPER if (row+col) % 2 == 0 else RED
            x, y = x0+col*cell, y0+row*cell
            draw.rectangle((x, y, x+cell, y+cell), fill=color)


def draw_master() -> Image.Image:
    img = Image.new("RGBA", (SIZE, SIZE), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)

    # 号码牌式八角外壳，区别于通用圆角方块。
    cut = 108
    d.polygon([(cut, 18), (SIZE-cut, 18), (SIZE-18, cut),
               (SIZE-18, SIZE-cut), (SIZE-cut, SIZE-18), (cut, SIZE-18),
               (18, SIZE-cut), (18, cut)], fill=INK)
    # 内圈细边只在四角断开，像印在维修站数据牌上的安全边。
    d.line([(155, 84), (869, 84), (940, 155)], fill=PANEL, width=12)
    d.line([(940, 869), (869, 940), (155, 940), (84, 869)], fill=PANEL, width=12)

    # 无线电呼叫牌：矩形主体与指向下方的尾部合成一个单色面。
    d.polygon([(174, 244), (245, 174), (714, 174), (790, 250),
               (790, 650), (715, 725), (620, 725), (478, 856),
               (500, 725), (245, 725), (174, 654)], fill=PAPER)

    # 三条“文本”：中间红色短句是被转换的本地化内容。
    d.rounded_rectangle((266, 314, 660, 370), radius=28, fill=INK)
    d.rounded_rectangle((266, 424, 570, 480), radius=28, fill=RED)
    d.rounded_rectangle((266, 534, 616, 590), radius=28, fill=INK)

    # 维修站无线电波：两段短弧从呼叫牌左侧探出，保持克制。
    d.arc((90, 360, 210, 480), start=210, end=330, fill=RED, width=24)
    d.arc((62, 324, 234, 516), start=210, end=330, fill=PAPER, width=16)

    # 方格旗从牌面右上角伸出：深色旗杆 + 红白棋盘，构成识别记忆点。
    d.rounded_rectangle((842, 118, 875, 430), radius=16, fill=RED)
    d.ellipse((832, 102, 886, 156), fill=PAPER)
    d.ellipse((847, 117, 871, 141), fill=RED)
    flag_box = (694, 176, 854, 336)
    d.rounded_rectangle((flag_box[0]-12, flag_box[1]-12,
                         flag_box[2]+12, flag_box[3]+12), radius=20, fill=INK)
    _checker(d, flag_box, 40)

    # 旗杆底端小红色圆头收住轮廓；避免做成箭头或斜纹。
    d.ellipse((831, 405, 887, 461), fill=RED)
    return img


def main() -> None:
    master = draw_master()
    master.resize((256, 256), Image.Resampling.LANCZOS).save(PREVIEW, "PNG", optimize=True)
    master.save(OUT, format="ICO", sizes=[(16, 16), (24, 24), (32, 32), (48, 48),
                                            (64, 64), (128, 128), (256, 256)])
    print("写出", OUT)
    print("预览", PREVIEW)


if __name__ == "__main__":
    main()
