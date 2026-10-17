#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
make_promo_png.py —— 生成手机端预览图（竖版 3:4 + 方版 1:1，PNG）。

为什么需要它：
    README / Pages 上的 SVG、横版 GIF 在部分移动端预览不佳。
    本脚本产出两张手机比例 PNG，内容与 assets/points-ladder.{gif,svg} 同源：

      1. promo-vertical.png  1080x1440 —— 竖版预览（3:4）
      2. promo-square.png    1080x1080 —— 方版预览（1:1）

设计约束（与 make_points_ladder.py / make_banner_svg.py 同一套原则）：
    1. 数字零手抄 —— 档位分界、解锁件数、另付现金、奖池、现值、总结论
       （27 = 9 真可兑 + 18 绝版）全部由 make_points_ladder.compute 与
       rank_products.classify 从 fixtures 实算，改数据重跑即可。
    2. 超宽护栏 —— 任何文字超出可用宽度显式报警（退出码 3），不静默截断。
    3. 品牌一致 —— 深棕黑底 + 麦当劳金 #FFC72C / 红 #DA291C，
       金拱门 path 与 make_banner_svg.py 同源（贝塞尔采样近似）。

用法:
    python make_promo_png.py                  # 两张都出
    python make_promo_png.py --vertical-only  # 只出竖版
    python make_promo_png.py --square-only    # 只出方版

依赖: Pillow。
"""

import argparse
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))

sys.path.insert(0, HERE)
from make_points_ladder import (  # noqa: E402
    compute, strip_price, CAT_FIXTURES, FIXTURES, snapshot_now, _bezier,
)
from rank_products import classify  # noqa: E402

from PIL import Image, ImageDraw, ImageFont  # noqa: E402

# 品牌色（与 make_points_ladder.py 同一套）
C_YELLOW_RGB = (255, 199, 44)
C_RED_RGB = (218, 41, 28)
BG_TOP_RGB = (32, 31, 41)
BG_BOT_RGB = (22, 21, 29)
CARD_RGB = (40, 38, 52)
FG_RGB = (232, 230, 223)
DIM_RGB = (140, 138, 130)
CORAL_RGB = (240, 153, 123)

FONT_CANDIDATES = [
    "C:/Windows/Fonts/Deng.ttf",
    "C:/Windows/Fonts/msyh.ttc",
    "C:/Windows/Fonts/simhei.ttf",
    "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
]

VW, VH = 1080, 1440     # 竖版 3:4
SW, SH = 1080, 1080     # 方版 1:1
MARGIN = 64             # 左右安全边距

# 金拱门控制点（与 make_banner_svg.py 的 ARCH_PATH 对应）
ARCH_SEGS = [((10, 92), (10, 22), (26, 10), (42, 10)),
             ((42, 10), (54, 10), (58, 24), (60, 50)),
             ((60, 50), (62, 24), (66, 10), (78, 10)),
             ((78, 10), (94, 10), (110, 22), (110, 92))]


def arch_points(scale, cx, top):
    """金拱门采样点：scale 缩放，cx 中心 x，top 顶点 y。"""
    pts = []
    for s in ARCH_SEGS:
        pts.extend(_bezier(*s))
    xs = [p[0] for p in pts]
    span = (max(xs) - min(xs)) * scale
    x0 = cx - span / 2 - min(xs) * scale
    return [(x0 + p[0] * scale, top + p[1] * scale) for p in pts]


def find_font():
    for p in FONT_CANDIDATES:
        if os.path.isfile(p):
            return p
    return None


# ---------------------------------------------------------------- 数据层
def bucket_stats():
    """合并逐类目快照 → classify 分桶（demo.py 同口径）。
    返回 {'redeemable': 9, 'extinct': 18, 'points_total': 27}。"""
    items = {}
    for name in CAT_FIXTURES:
        with open(os.path.join(FIXTURES, name), encoding="utf-8") as f:
            raw = f.read()
        for it in json.loads(raw).get("data", raw):
            items.setdefault(it.get("spuId"), it)
    now = snapshot_now()
    buckets = {"redeemable": 0, "extinct": 0, "cash_only": 0, "unknown_expiry": 0}
    for it in items.values():
        b, _ = classify(it, now)
        buckets[b] += 1
    buckets["points_total"] = buckets["redeemable"] + buckets["extinct"]
    return buckets


def ladder_rows(data):
    """天梯行（竖版/方版共用）：[(积分, 主文案, 次文案, 次文案色)]。"""
    rows = []
    for t in data["tiers"]:
        if t["is_lottery"]:
            rows.append((
                t["threshold"],
                "解锁抽奖资格 · %d 品奖池" % data["lottery"]["prize_count"],
                "最高回血 %d 分" % data["lottery"]["max_back"],
                CORAL_RGB,
            ))
            continue
        best = min(t["items"], key=lambda m: (m.get("unit_price") is None,
                                              m.get("unit_price") or 0))
        name = strip_price(best["name"])
        sub = "另付 ¥%.1f 起" % t["cash_min"] if t["cash_min"] is not None else "纯积分可兑"
        rows.append((
            t["threshold"],
            "解锁 %d 件 · %s" % (t["unlocked"], name),
            sub,
            CORAL_RGB if t["cash_min"] is not None else C_YELLOW_RGB,
        ))
    return rows


# ---------------------------------------------------------------- 绘制
def draw_background(img, top_rgb, bot_rgb):
    """竖向渐变背景（逐行插值，无第三方依赖）。"""
    d = ImageDraw.Draw(img)
    h = img.height
    for y in range(h):
        t = y / max(1, h - 1)
        c = tuple(int(top_rgb[i] + (bot_rgb[i] - top_rgb[i]) * t) for i in range(3))
        d.line([(0, y), (img.width, y)], fill=c)


def draw_arch(d, scale, cx, top, color, width):
    d.line(arch_points(scale, cx, top), fill=color, width=width, joint="curve")


def text_w(d, s, font):
    return d.textlength(s, font=font)


def centered_on(d, canvas_w, y, s, font, fill, stroke=0, stroke_fill=None):
    w = text_w(d, s, font)
    d.text(((canvas_w - w) / 2, y), s, font=font, fill=fill,
           stroke_width=stroke, stroke_fill=stroke_fill or fill)


def check_fit(tag, items, limit):
    """超宽护栏：[(文本, 实测宽)] 超限即报。返回是否通过。"""
    bad = [(s, w) for s, w in items if w > limit]
    for s, w in bad:
        print("⚠️ [%s] 文字超宽 %.0fpx（限 %d）：%s" % (tag, w, limit, s))
    return not bad


def render_vertical(font_path, data, stats, out_path):
    f_title = ImageFont.truetype(font_path, 86)
    f_brand = ImageFont.truetype(font_path, 38)
    f_sub = ImageFont.truetype(font_path, 26)
    f_pts = ImageFont.truetype(font_path, 38)
    f_main = ImageFont.truetype(font_path, 34)
    f_minor = ImageFont.truetype(font_path, 26)
    f_concl = ImageFont.truetype(font_path, 42)
    f_concl_big = ImageFont.truetype(font_path, 46)
    f_foot = ImageFont.truetype(font_path, 28)
    f_tiny = ImageFont.truetype(font_path, 20)

    rows = ladder_rows(data)
    concl_1 = "%d 件标着“上架”，%d 件兑换窗口早关了" % (
        stats["points_total"], stats["extinct"])
    concl_2 = "%d 件真能兑，没有一件是纯积分白拿" % stats["redeemable"]
    concl_3 = "每 100 积分账面现值 ¥%.2f" % data["value_per_100"]

    # ---- 护栏预检（画前测宽，超宽直接退出码 3）
    probe = ImageDraw.Draw(Image.new("RGB", (8, 8)))
    fits = []
    for s, f in [("你有多少积分", f_title), ("掌柜就怎么答", f_title),
                 (concl_1, f_concl), (concl_2, f_concl_big), (concl_3, f_sub),
                 ("GitHub 搜 mc-points-steward", f_foot)]:
        fits.append((s, text_w(probe, s, f)))
    row_w = []
    for pts, main, minor, _ in rows:
        row_w.append(("%d 分" % pts, text_w(probe, "%d 分" % pts, f_pts)))
        row_w.append((main, text_w(probe, main, f_main)))
        row_w.append((minor, text_w(probe, minor, f_minor)))
    if not check_fit("vertical", fits, VW - 2 * MARGIN):
        return 3
    if not check_fit("vertical-row", row_w, VW - MARGIN - 256 - 24):
        return 3

    # ---- 作画
    img = Image.new("RGB", (VW, VH), BG_TOP_RGB)
    draw_background(img, BG_TOP_RGB, BG_BOT_RGB)
    d = ImageDraw.Draw(img)

    # 顶部：金拱门 + 品牌
    draw_arch(d, 0.62, VW // 2, 44, C_YELLOW_RGB, 11)
    centered_on(d, VW, 196, "麦享掌柜 mc-points-steward", f_brand, C_YELLOW_RGB,
                stroke=1, stroke_fill=C_YELLOW_RGB)
    centered_on(d, VW, 250, "麦当劳中国 MCP 开发者创新大赛参赛作品", f_sub, DIM_RGB)

    # 主标题
    centered_on(d, VW, 316, "你有多少积分", f_title, FG_RGB,
                stroke=1, stroke_fill=FG_RGB)
    centered_on(d, VW, 418, "掌柜就怎么答", f_title, C_YELLOW_RGB,
                stroke=1, stroke_fill=C_YELLOW_RGB)
    centered_on(d, VW, 528, "麦当劳积分商城实测 · 2026-10-12", f_sub, DIM_RGB)

    # 天梯六行
    row_h, row_gap, box_h = 88, 0, 80
    y = 584
    for pts, main, minor, minor_color in rows:
        d.rounded_rectangle([MARGIN, y, VW - MARGIN, y + box_h],
                            radius=16, fill=CARD_RGB)
        # 积分胶囊
        cap = "%d 分" % pts
        cw = text_w(d, cap, f_pts) + 40
        d.rounded_rectangle([MARGIN + 20, y + 14, MARGIN + 20 + cw, y + box_h - 14],
                            radius=22, outline=C_YELLOW_RGB, width=2)
        d.text((MARGIN + 40, y + (box_h - 38) / 2), cap, font=f_pts,
               fill=C_YELLOW_RGB)
        # 右侧主/次文案
        tx = MARGIN + 20 + cw + 28
        d.text((tx, y + 8), main, font=f_main, fill=FG_RGB)
        d.text((tx, y + 46), minor, font=f_minor, fill=minor_color)
        y += row_h + row_gap

    # 结论区
    d.line([(MARGIN, 1140), (VW - MARGIN, 1140)], fill=(96, 82, 44), width=2)
    centered_on(d, VW, 1174, concl_1, f_concl, FG_RGB)
    centered_on(d, VW, 1236, concl_2, f_concl_big, C_YELLOW_RGB,
                stroke=1, stroke_fill=C_YELLOW_RGB)
    centered_on(d, VW, 1306, concl_3, f_sub, DIM_RGB)

    # 底部
    centered_on(d, VW, 1356, "GitHub 搜 mc-points-steward", f_foot, FG_RGB)
    centered_on(d, VW, 1400, "数据来自 2026-10-12 真实商城调用 · 数字零手抄",
                f_tiny, DIM_RGB)

    img.save(out_path, "PNG")
    return 0


def render_square(font_path, data, stats, out_path):
    f_title = ImageFont.truetype(font_path, 54)
    f_brand = ImageFont.truetype(font_path, 34)
    f_pts = ImageFont.truetype(font_path, 30)
    f_main = ImageFont.truetype(font_path, 28)
    f_minor = ImageFont.truetype(font_path, 22)
    f_concl = ImageFont.truetype(font_path, 38)
    f_concl_big = ImageFont.truetype(font_path, 40)
    f_foot = ImageFont.truetype(font_path, 26)
    f_tiny = ImageFont.truetype(font_path, 18)

    rows = ladder_rows(data)
    concl_1 = "%d 件标着“上架”，%d 件兑换窗口早关了" % (
        stats["points_total"], stats["extinct"])
    concl_2 = "%d 件真能兑，没有一件是纯积分白拿" % stats["redeemable"]
    concl_3 = "每 100 积分账面现值 ¥%.2f · GitHub 搜 mc-points-steward" % (
        data["value_per_100"])

    # ---- 护栏预检
    probe = ImageDraw.Draw(Image.new("RGB", (8, 8)))
    fits = [("你有多少积分，掌柜就怎么答", f_title),
            (concl_1, f_concl), (concl_2, f_concl_big), (concl_3, f_foot)]
    if not check_fit("square",
                     [(s, text_w(probe, s, f)) for s, f in fits],
                     SW - 2 * MARGIN):
        return 3
    row_w = []
    for pts, main, minor, _ in rows:
        row_w.append((main, text_w(probe, main, f_main)))
    if not check_fit("square-row", row_w, SW - MARGIN - 220 - 24):
        return 3

    # ---- 作画
    img = Image.new("RGB", (SW, SH), BG_TOP_RGB)
    draw_background(img, BG_TOP_RGB, BG_BOT_RGB)
    d = ImageDraw.Draw(img)

    draw_arch(d, 0.48, SW // 2, 36, C_YELLOW_RGB, 9)
    centered_on(d, SW, 140, "麦享掌柜 mc-points-steward", f_brand, C_YELLOW_RGB)
    centered_on(d, SW, 196, "你有多少积分，掌柜就怎么答", f_title, FG_RGB,
                stroke=1, stroke_fill=FG_RGB)

    row_h, box_h = 82, 74
    y = 288
    for pts, main, minor, minor_color in rows:
        d.rounded_rectangle([MARGIN, y, SW - MARGIN, y + box_h],
                            radius=14, fill=CARD_RGB)
        cap = "%d 分" % pts
        d.text((MARGIN + 22, y + (box_h - 30) / 2), cap, font=f_pts,
               fill=C_YELLOW_RGB)
        d.text((MARGIN + 168, y + 10), main, font=f_main, fill=FG_RGB)
        d.text((MARGIN + 168, y + 42), minor, font=f_minor, fill=minor_color)
        y += row_h

    d.line([(MARGIN, y + 14), (SW - MARGIN, y + 14)], fill=(96, 82, 44), width=2)
    centered_on(d, SW, y + 40, concl_1, f_concl, FG_RGB)
    centered_on(d, SW, y + 92, concl_2, f_concl_big, C_YELLOW_RGB,
                stroke=1, stroke_fill=C_YELLOW_RGB)
    centered_on(d, SW, y + 150, concl_3, f_foot, DIM_RGB)
    centered_on(d, SW, SH - 40, "数据来自 2026-10-12 真实商城调用 · 数字零手抄",
                f_tiny, DIM_RGB)

    img.save(out_path, "PNG")
    return 0


def main(argv=None):
    ap = argparse.ArgumentParser(description="生成手机端预览图（竖版 + 方版 PNG）")
    ap.add_argument("--vertical-only", action="store_true", help="只出竖版")
    ap.add_argument("--square-only", action="store_true", help="只出方版")
    ap.add_argument("--out-vertical",
                    default=os.path.join(ROOT, "assets", "promo-vertical.png"))
    ap.add_argument("--out-square",
                    default=os.path.join(ROOT, "assets", "promo-square.png"))
    args = ap.parse_args(argv)

    font_path = find_font()
    if not font_path:
        print("⚠️ 找不到中文字体（Deng.ttf / msyh.ttc / simhei.ttf / Noto CJK）")
        return 2

    data = compute()
    stats = bucket_stats()
    rows = ladder_rows(data)
    print("天梯 %d 级：%s" % (len(rows),
          " / ".join("%d分" % r[0] for r in rows)))
    print("总结论实算：%d 件上架 = %d 真可兑 + %d 绝版；现值 %.2f 元/100分"
          % (stats["points_total"], stats["redeemable"],
             stats["extinct"], data["value_per_100"]))

    if args.vertical_only and args.square_only:
        print("⚠️ --vertical-only 与 --square-only 不能同时用")
        return 2

    rc = 0
    if not args.square_only:
        rc = render_vertical(font_path, data, stats,
                             os.path.abspath(args.out_vertical))
        if rc == 0:
            print("已生成 %s（%dx%d）" % (os.path.abspath(args.out_vertical),
                                         VW, VH))
    if not args.vertical_only:
        rc = render_square(font_path, data, stats,
                           os.path.abspath(args.out_square))
        if rc == 0:
            print("已生成 %s（%dx%d）" % (os.path.abspath(args.out_square),
                                         SW, SH))
    return rc


if __name__ == "__main__":
    sys.exit(main())
