#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
积分解锁天梯测试（make_points_ladder.py）。

守四件事：
    ① 数据层 —— 天梯阈值、解锁件数、抽奖口径全部由 fixtures 实算，
       且与 rank_products 主口径一致（不是第二套数字）；
    ② SVG 合法性 —— 无 RGB 元组泄漏（fill="(232, 230, 223)" 这种）、
       无坐标越界（踩过：末档刻度 x=861 超出画布 860）；
    ③ GIF 合法性 —— 生成器退出码 0（含超宽护栏）、产出是合法 GIF；
    ④ 护栏生效 —— 人为制造超宽文案时退出码为 3，不是静默截断。

运行:
    python tests/test_points_ladder.py
"""

import os
import re
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, ".."))
SCRIPT = os.path.join(ROOT, "scripts", "make_points_ladder.py")
ASSETS = os.path.join(os.path.dirname(ROOT), "assets")
SVG_OUT = os.path.join(ASSETS, "points-ladder.svg")
GIF_OUT = os.path.join(ASSETS, "points-ladder.gif")
PASS, FAIL = 0, 0


def check(name, got, want):
    global PASS, FAIL
    if got == want:
        PASS += 1
        print(f"  ✓ {name}")
    else:
        FAIL += 1
        print(f"  ✗ {name}\n      got={got!r} want={want!r}")


def main():
    sys.path.insert(0, os.path.join(ROOT, "scripts"))
    from make_points_ladder import (  # noqa: E402
        compute, build_svg, CARD_W, CARD_H, W, H, card_lines,
    )

    data = compute()
    tiers = data["tiers"]

    print("== 1. 天梯数据层（全部由 fixtures 实算） ==")
    check("阈值 = [24,50,100,200,500,800]（抽奖门槛+商品档位）",
          [t["threshold"] for t in tiers], [24, 50, 100, 200, 500, 800])
    check("首级是抽奖级", tiers[0]["is_lottery"], True)
    check("解锁件数累计 = 2/4/6/8/9",
          [t["unlocked"] for t in tiers[1:]], [2, 4, 6, 8, 9])
    check("末级解锁全部 9 件", tiers[-1]["unlocked"], 9)
    check("抽奖口径：24 分/次", data["lottery"]["draw_point"], 24)
    check("抽奖口径：奖池 10 品", data["lottery"]["prize_count"], 10)
    check("抽奖口径：最高回血 30 分", data["lottery"]["max_back"], 30)
    check("现值口径：每 100 分 ¥13.79", data["value_per_100"], 13.79)
    check("同名陷阱检出 1 组（指定小食任选 100/200）",
          data["traps"], [("10.9元指定小食任选", [100, 200])])
    # 每级 cash_min 与 new_items 实际另付一致（防 apply_detail 漏挂）
    for t in tiers[1:]:
        expect = min(m["cash_on_top"] for m in t["items"])
        check("%d 分档另付最小值 = %.1f" % (t["threshold"], expect),
              t["cash_min"], expect)

    print("== 2. 卡片文案（宽度护栏内的四行结构） ==")
    lines = card_lines(tiers[2], data)   # 100 分档：4 行
    check("兑换级 4 行", len(lines), 4)
    check("行1 是积分值（金色加粗）", (lines[0][0], lines[0][2], lines[0][3]),
          ("100 分", "#FFC72C", True))
    check("行2 是解锁件数", lines[1][0], "解锁 4 件可兑")
    check("抽奖级 4 行（资格/单价品数/回血）",
          [l[0] for l in card_lines(tiers[0], data)],
          ["24 分", "解锁抽奖资格", "24分/次·10品", "最高回血30分"])
    # 颜色必须是 hex（SVG 直接用；踩过 RGB 元组泄漏进 fill）
    hexes = all(re.fullmatch(r"#[0-9A-Fa-f]{6}", l[2]) for t in tiers
                for l in card_lines(t, data))
    check("所有卡片颜色为 hex 格式", hexes, True)

    print("== 3. SVG 合法性与坐标越界防线 ==")
    svg = build_svg(data)
    check("无 RGB 元组泄漏（fill=\"(...)\"）", bool(re.search(r'fill="\(', svg)), False)
    check("无 NaN/None 泄漏", bool(re.search(r'>(None|nan)<', svg)), False)
    xs = [float(m) for m in re.findall(r'(?:^|\s)(?:x|cx|x1|x2)="([\d.]+)"', svg)]
    check("所有 x 类坐标 <= 画布宽", all(x <= W for x in xs), True)
    rects = re.findall(r'<rect x="([\d.]+)"[^>]*width="(\d+)"', svg)
    check("所有 rect 右边界 <= 画布宽",
          all(float(a) + float(b) <= W for a, b in rects), True)
    check("所有 rect 底边界 <= 画布高",
          all(float(m[0]) + float(m[1]) <= H
              for m in re.findall(r'<rect x="[\d.]+" y="([\d.]+)"[^>]*height="(\d+)"',
                                  svg)), True)
    for t in tiers:
        check("SVG 含 %d 分档卡片" % t["threshold"],
              (">%d 分<" % t["threshold"]) in svg, True)
    check("SVG 含现值折算", "¥13.79" in svg, True)
    check("SVG 含同名陷阱注释", "同名不同分" in svg, True)
    check("SVG 含金拱门 path", "C 54 10 58 24 60 50" in svg, True)

    print("== 4. 生成器端到端（SVG + GIF，含护栏） ==")
    p = subprocess.run([sys.executable, SCRIPT],
                       capture_output=True, text=True, encoding="utf-8")
    check("退出码 0（非 0 即护栏或渲染出问题）", p.returncode, 0)
    check("SVG 落盘", os.path.isfile(SVG_OUT), True)
    check("GIF 落盘", os.path.isfile(GIF_OUT), True)
    try:
        from PIL import Image
        im = Image.open(GIF_OUT)
        ok = im.format == "GIF"
        frames, size = im.n_frames, im.size
    except Exception as e:
        ok, frames, size = False, 0, (0, 0)
        print("     打开失败:", e)
    check("PIL 识别为 GIF", ok, True)
    check("帧数 ≥ 80（打字机+轴线+6 卡滑入）", frames >= 80, True)
    check("画布 860x400", size, (860, 400))

    print("== 5. 护栏生效性（超宽文案必须被识别，不静默截断） ==")
    # 直接调护栏函数造一条超宽文案，验证判定逻辑本身
    from make_points_ladder import gif_overflow, CARD_W as CW
    from PIL import Image, ImageDraw, ImageFont
    probe = ImageDraw.Draw(Image.new("RGB", (8, 8)))
    fp = None
    for c in ["C:/Windows/Fonts/Deng.ttf", "C:/Windows/Fonts/msyh.ttc",
              "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc"]:
        if os.path.isfile(c):
            fp = c
            break
    if fp:
        f = ImageFont.truetype(fp, 12)
        check("超宽字符串确实超过卡片可用宽",
              probe.textlength("超宽" * 20, font=f) > CW - 24, True)
        check("正常卡片文案不触护栏", gif_overflow(data, probe, (f, f, f, f)), [])
        # 人为构造超宽 tier，护栏必须报出来（否则就是静默截断）
        fake = [dict(tiers[1], items=tiers[1]["items"])]
        fake_lines_orig = card_lines

        def fake_lines(t, d):
            ls = list(fake_lines_orig(t, d))
            ls[2] = ("超宽测试文案" * 8, 11, "#FFFFFF", False)
            return ls
        import make_points_ladder as M
        M.card_lines = fake_lines
        try:
            n_bad = len(gif_overflow({"tiers": fake}, probe, (f, f, f, f)))
        finally:
            M.card_lines = fake_lines_orig
        check("人为超宽文案会被护栏捕获", n_bad, 1)

    print(f"\n{'ALL PASS' if FAIL == 0 else 'HAS FAILURE'}  通过 {PASS} / 失败 {FAIL}")
    return 1 if FAIL else 0


if __name__ == "__main__":
    sys.exit(main())
