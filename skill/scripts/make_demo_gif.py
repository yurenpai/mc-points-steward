#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
make_demo_gif.py —— 合成「终端录屏风」演示 GIF。

为什么这么做：
    动态演示比静态截图多一层「它在真的跑」的说服力。我们没有录屏条件，
    但可以**用真实输出逐帧合成**——文字与 `python scripts/demo.py` 的实际
    输出逐字一致，只是做了片段截取与打字机效果。

设计约束（与 make_report_svg.py 同一套原则）：
    1. 文字零手抄 —— 全部行取自 demo.py 的 subprocess 实跑输出，只做「选行」不改字。
    2. 选行只按关键词过滤，过滤规则写死在 KEY_LINES 里，可复查。
    3. 输出自包含 GIF，无外部依赖。

用法:
    python make_demo_gif.py                 # 输出 <仓库根>/assets/demo.gif
    python make_demo_gif.py --out x.gif     # 指定路径
    python make_demo_gif.py --scale 0.5     # 缩放（默认 1.0）

依赖: Pillow（PIL）。未安装时给出明确提示，不静默失败。
"""

import argparse
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))

FONT_CANDIDATES = [
    "C:/Windows/Fonts/Deng.ttf",        # 等线（中英混排，Win10+ 自带）
    "C:/Windows/Fonts/msyh.ttc",        # 微软雅黑（兜底）
    "C:/Windows/Fonts/simhei.ttf",
]

# 选行关键词：命中任一即保留该行（文字不改，只决定展示哪些行）。
# 踩过的坑：早期用「奖池」「优惠券」「麦乐鸡」等泛词，导致 9 张优惠券被逐行
# 刷屏、孤立行「② 抽奖回血」突兀出现、一行 60+ 字的超宽行溢出画布。
# 现在的关键词都指向「叙事必需行」，宁可少也不错。
KEY_LINES = [
    "积分账本", "可用积分", "资产现值", "每 100 积分现值",
    "真实可兑榜单", "件在售", "默认查询漏报", "16.9元2份麦辣鸡翅", "圆筒冰淇淋",
    "可乐麦炫酷", "隐藏现金成本", "纯积分白拿", "另付区间",
    "积分抽奖", "奖池 10 品", "资格判定", "可以抽", "暂不可抽", "分换 30 分",
]

CMD = "$ python scripts/demo.py"

# 终端配色（深色底，微信/GitHub 均按深色呈现）
BG = (30, 29, 38)
BAR = (48, 46, 60)
FG = (232, 230, 223)
DIM = (140, 138, 130)
YELLOW = (255, 199, 44)
CYAN = (127, 209, 245)
CORAL = (240, 153, 123)
GREEN = (130, 200, 140)


def find_font():
    for p in FONT_CANDIDATES:
        if os.path.isfile(p):
            return p
    return None


def run_demo():
    p = subprocess.run([sys.executable, os.path.join(HERE, "demo.py")],
                       capture_output=True, text=True, encoding="utf-8")
    if p.returncode != 0:
        raise RuntimeError("demo.py 运行失败: %s" % p.stderr[:300])
    return p.stdout


def pick_lines(out):
    """按关键词选行。保序、去重、去空白行。"""
    seen, picked = set(), []
    for line in out.splitlines():
        s = line.rstrip()
        if not s.strip():
            continue
        if any(k in s for k in KEY_LINES) and s not in seen:
            seen.add(s)
            picked.append(s)
    return picked


def render(cmd_text, visible_lines, font, W, H, cursor=False):
    """渲染一帧。"""
    from PIL import Image, ImageDraw
    img = Image.new("RGB", (W, H), BG)
    d = ImageDraw.Draw(img)

    # 标题栏
    d.rectangle([0, 0, W, 26], fill=BAR)
    for i, c in enumerate(((238, 95, 88), (245, 190, 80), (120, 200, 120))):
        d.ellipse([14 + i * 18, 9, 24 + i * 18, 19], fill=c)
    d.text((70, 7), "麦享掌柜 · mc-points-steward", font=font, fill=DIM)

    y = 40
    # 命令行（打字机效果由 cmd_text 长度控制）
    if cmd_text:
        d.text((16, y), cmd_text, font=font, fill=FG)
        if cursor:
            w = d.textlength(cmd_text, font=font)
            d.rectangle([16 + w + 2, y + 2, 16 + w + 9, y + 15], fill=YELLOW)
        y += 26

    # 输出行
    for line in visible_lines:
        color = FG
        if "到店另付" in line or "☠" in line or "⚠" in line:
            color = CORAL
        elif "¥" in line or "现值" in line:
            color = YELLOW
        elif "件" in line and ("在售" in line or "真能兑" in line):
            color = GREEN
        elif line.strip().startswith(("──", "╔", "╚", "──")):
            color = DIM
        d.text((16, y), line, font=font, fill=color)
        y += 20

    # 末尾光标
    if cursor and not cmd_text:
        d.rectangle([16, y + 2, 23, y + 15], fill=YELLOW)
    return img


def main():
    ap = argparse.ArgumentParser(description="合成终端风演示 GIF")
    ap.add_argument("--out", default=None, help="输出路径，默认 <仓库根>/assets/demo.gif")
    ap.add_argument("--scale", type=float, default=1.0, help="画面缩放，默认 1.0")
    ap.add_argument("--line-ms", type=int, default=130, help="每行输出间隔毫秒")
    args = ap.parse_args()

    try:
        from PIL import Image, ImageFont
    except ImportError:
        print("需要 Pillow：pip install Pillow")
        return 2

    font_path = find_font()
    if not font_path:
        print("找不到中文字体（试过 %s）" % ", ".join(FONT_CANDIDATES))
        return 2

    font = ImageFont.truetype(font_path, 13)
    lines = pick_lines(run_demo())
    if not lines:
        print("选行结果为空，检查 KEY_LINES")
        return 2

    W, H = 700, 40 + 26 + len(lines) * 20 + 30

    # 护栏：超宽行会溢出画布。显式报警，不静默截断——数据变了要让人知道。
    overflow = [l for l in lines if font.getlength(l) > W - 32]
    if overflow:
        print("⚠️ %d 行超出画布宽度 %d，请调整 KEY_LINES 或缩小字号：" % (len(overflow), W))
        for l in overflow:
            print("   [%dpx] %s" % (font.getlength(l), l[:50]))
        return 3

    frames = []

    # 1) 空终端 + 光标
    for _ in range(4):
        frames.append(render("", [], font, W, H, cursor=True))

    # 2) 命令逐字符
    for i in range(1, len(CMD) + 1):
        frames.append(render(CMD[:i], [], font, W, H))

    # 3) 回车，命令定稿
    for _ in range(3):
        frames.append(render(CMD, [], font, W, H, cursor=True))

    # 4) 输出逐行
    for i in range(1, len(lines) + 1):
        frames.append(render(CMD, lines[:i], font, W, H))

    # 5) 结尾停留 + 光标
    for _ in range(6):
        frames.append(render(CMD, lines, font, W, H, cursor=True))

    if args.scale != 1.0:
        W2, H2 = int(W * args.scale), int(H * args.scale)
        frames = [f.resize((W2, H2)) for f in frames]
        W, H = W2, H2

    out = args.out or os.path.join(os.path.dirname(os.path.dirname(HERE)),
                                   "assets", "demo.gif")
    os.makedirs(os.path.dirname(out), exist_ok=True)

    durations = ([180] * 4
                 + [55] * len(CMD)
                 + [180] * 3
                 + [args.line_ms] * len(lines)
                 + [220] * 6)
    frames[0].save(out, save_all=True, append_images=frames[1:],
                   duration=durations, loop=0, optimize=True)

    total_ms = sum(durations)
    print("已生成 %s（%d 帧，%.1f 秒，%d 字节）"
          % (out, len(frames), total_ms / 1000.0, os.path.getsize(out)))
    print("展示 %d 行真实输出（选自 demo.py 实跑，文字未改）" % len(lines))
    return 0


if __name__ == "__main__":
    sys.exit(main())
