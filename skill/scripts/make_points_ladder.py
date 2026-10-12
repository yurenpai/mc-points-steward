#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
make_points_ladder.py —— 合成「积分解锁天梯」宣传物料（GIF + SVG 双产物）。

为什么这么做：
    宣传的核心不是「我做了个 Skill」，而是「不同积分余额的人，拿到的是
    完全不同的答案」。本项目 9 件真可兑商品的积分档位天然是
    50 / 100 / 200 / 500 / 800，加上抽奖门槛 24 分——一条「解锁天梯」
    直接从真实数据里长出来，不需要编。

设计约束（与 make_banner_svg.py / make_demo_gif.py 同一套原则）：
    1. 数字零手抄 —— 档位分界、解锁件数、另付现金、现值折算全部由
       rank_products.classify + points_value 从 fixtures 实算。
    2. 档位由数据推导 —— 阈值不是硬编码的，是 redeemable 商品 point
       去重升序 + 抽奖 drawPoint；数据变了图自动跟着变。
    3. 超宽护栏 —— 卡片文字超出画布显式报警（退出码 3），不静默截断。
    4. 自包含 —— SVG 内联手绘金拱门（path 与 make_banner_svg.py 同源），
       GIF 用同一 path 的贝塞尔采样近似，不引外部图片/字体。

用法:
    python make_points_ladder.py                  # 输出 assets/points-ladder.{gif,svg}
    python make_points_ladder.py --scale 0.85     # GIF 缩放
    python make_points_ladder.py --svg-only       # 只出 SVG（无需 Pillow）

依赖: Pillow（仅 GIF 需要）。SVG 与数据层纯标准库。
"""

import argparse
import json
import os
import re
import sys
from datetime import datetime

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
FIXTURES = os.path.join(os.path.dirname(HERE), "tests", "fixtures")

sys.path.insert(0, HERE)
from rank_products import (  # noqa: E402
    classify, TIME_FMT, load_details, apply_detail, points_value,
)

CAT_FIXTURES = [
    "mall_products_cat_1_4_20261012.json",   # 商品券 1>4
    "mall_products_cat_2_8_20261012.json",   # 周边 2>8
]
LOTTERY_FIXTURE = "lottery_info_20261012.json"
DETAIL_FIXTURE = "mall_details_20261012.json"

# 品牌色（与 make_banner_svg.py 同一套）。SVG 用 hex，GIF 用 rgb。
C_YELLOW = "#FFC72C"
C_RED = "#DA291C"
FG_HEX, DIM_HEX, CORAL_HEX = "#E8E6DF", "#8C8A82", "#F0997B"
BG_RGB = (30, 29, 38)
CARD_RGB = (38, 36, 50)
FG_RGB, DIM_RGB, YELLOW_RGB, CORAL_RGB = (232, 230, 223), (140, 138, 130), (255, 199, 44), (240, 153, 123)


def rgb_of(hx):
    """'#RRGGBB' → (r, g, b)。"""
    return tuple(int(hx[i:i + 2], 16) for i in (1, 3, 5))

# 金拱门 path（与 make_banner_svg.py 逐字一致，粗圆头笔画）
ARCH_PATH = ("M 10 92 C 10 22 26 10 42 10 C 54 10 58 24 60 50 "
             "C 62 24 66 10 78 10 C 94 10 110 22 110 92")

W, H = 860, 400          # 画布（GIF 与 SVG 同布局）
AXIS_Y = 232             # 横轴 y
AXIS_X0, AXIS_X1 = 122, 738   # 轴两端内收半个卡片宽，防首尾卡片出画布
CARD_W, CARD_H = 148, 92
CARD_GAP_UP = 28         # 上卡片底边距轴
CARD_GAP_DOWN = 28       # 下卡片顶边距轴

FONT_CANDIDATES = [
    "C:/Windows/Fonts/Deng.ttf",
    "C:/Windows/Fonts/msyh.ttc",
    "C:/Windows/Fonts/simhei.ttf",
    "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
    "/usr/share/fonts/truetype/noto/NotoSansCJK-Regular.ttc",
]

PRICE_PREFIX = re.compile(r"^\d+(?:\.\d+)?元")


# ---------------------------------------------------------------- 数据层
def _load(name):
    with open(os.path.join(FIXTURES, name), "r", encoding="utf-8") as f:
        raw = json.load(f)
    return raw.get("data", raw)


def snapshot_now():
    """基准时间优先取快照 meta，保证 CI 复现（与 make_banner_svg.py 同口径）。"""
    try:
        with open(os.path.join(FIXTURES, "_meta_20261012.json"),
                  encoding="utf-8") as f:
            meta = json.load(f)
        return datetime.strptime(meta["now"], TIME_FMT)
    except Exception:
        return datetime(2026, 10, 12, 12, 0, 0)


def load_redeemable():
    """合并逐类目快照 → classify → 补详情。返回真可兑 meta 列表。"""
    items = {}
    for name in CAT_FIXTURES:
        for it in _load(name):
            items.setdefault(it.get("spuId"), it)
    now = snapshot_now()
    details = load_details([os.path.join(FIXTURES, DETAIL_FIXTURE)])
    out = []
    for it in items.values():
        bucket, meta = classify(it, now)
        if bucket != "redeemable":
            continue
        d = details.get(it.get("spuId"))
        if d:
            apply_detail(meta, d)
        out.append(meta)
    return out


def load_lottery():
    d = _load(LOTTERY_FIXTURE)
    prizes = d.get("prizes", []) or []
    draw_point = int(d.get("drawPoint", 0) or 0)
    backs = [int(m.group(1)) for p in prizes
             if p.get("typeText") == "积分奖"
             for m in [re.search(r"(\d+)", p.get("name", ""))] if m]
    return {
        "draw_point": draw_point,
        "prize_count": len(prizes),
        "max_back": max(backs) if backs else 0,
    }


def strip_price(name):
    return PRICE_PREFIX.sub("", name)


def build_tiers(redeemable, lottery):
    """由真实档位推导天梯。抽奖门槛若低于最低兑换档，作为第一级。"""
    thresholds = sorted(set(m["point"] for m in redeemable))
    if lottery["draw_point"] and (not thresholds or lottery["draw_point"] < thresholds[0]):
        thresholds = [lottery["draw_point"]] + thresholds

    tiers = []
    for i, th in enumerate(thresholds):
        unlocked = [m for m in redeemable if m["point"] <= th]
        new_items = [m for m in redeemable if m["point"] == th]
        cash = [m.get("cash_on_top") for m in new_items if m.get("cash_on_top")]
        tiers.append({
            "threshold": th,
            "is_lottery": bool(lottery["draw_point"]) and th == lottery["draw_point"],
            "unlocked": len(unlocked),
            "items": new_items,
            "names": [strip_price(m["name"]) for m in new_items],
            "cash_min": min(cash) if cash else None,
            "range_to": (thresholds[i + 1] - 1) if i + 1 < len(thresholds) else None,
        })
    return tiers


def name_traps(redeemable):
    """同名不同分陷阱（与 rank_products 主输出同口径）。"""
    by_name = {}
    for m in redeemable:
        by_name.setdefault(m["name"], []).append(m["point"])
    return sorted(((n, sorted(set(ps))) for n, ps in by_name.items() if len(set(ps)) > 1))


def compute():
    redeemable = load_redeemable()
    lottery = load_lottery()
    tiers = build_tiers(redeemable, lottery)
    pv = points_value(redeemable, None) or {}
    return {
        "redeemable": redeemable,
        "lottery": lottery,
        "tiers": tiers,
        "value_per_100": pv.get("value_per_100"),
        "best_rate": pv.get("best_rate_per_yuan"),
        "traps": name_traps(redeemable),
    }


# ---------------------------------------------------------------- SVG
def arch_svg(ox, oy, scale, color=C_YELLOW, glow=False):
    g = '<g transform="translate(%d,%d) scale(%.2f)"' % (ox, oy, scale)
    if glow:
        g += ' filter="url(#glow)"'
    g += ('><path d="%s" fill="none" stroke="%s" stroke-width="16" '
          'stroke-linecap="round" stroke-linejoin="round"/></g>'
          % (ARCH_PATH, color))
    return g


def build_svg(data):
    tiers = data["tiers"]
    n = len(tiers)                           # 刻度数 = 档位数 + 1（含 0）
    step = (AXIS_X1 - AXIS_X0) / n
    x_of = lambda i: AXIS_X0 + i * step      # noqa: E731

    S = []
    S.append('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 %d %d" '
             'width="%d" height="%d" font-family="PingFang SC, Microsoft YaHei, '
             'Noto Sans CJK SC, sans-serif">' % (W, H, W, H))
    S.append('<title>积分解锁天梯 · 麦享掌柜</title>')
    S.append('<desc>不同积分区间下 Skill 给出的不同决策。档位分界与解锁件数 '
             '全部来自 2026-10-12 真实商城数据实算。</desc>')
    S.append('<defs>'
             '<linearGradient id="axis" x1="0" y1="0" x2="1" y2="0">'
             '<stop offset="0" stop-color="%s"/><stop offset="1" stop-color="%s"/>'
             '</linearGradient>'
             '<filter id="glow" x="-50%%" y="-50%%" width="200%%" height="200%%">'
             '<feGaussianBlur stdDeviation="3" result="b"/>'
             '<feMerge><feMergeNode in="b"/><feMergeNode in="SourceGraphic"/>'
             '</feMerge></filter>'
             '</defs>' % (C_YELLOW, C_RED))
    S.append('<rect width="%d" height="%d" rx="12" fill="#1E1D26"/>' % (W, H))

    # 标题 + 金拱门
    S.append('<text x="24" y="34" font-size="21" font-weight="700" fill="%s">'
             '你有多少积分，掌柜就怎么答</text>' % C_YELLOW)
    S.append(arch_svg(W - 62, 8, 0.55, glow=True))
    sub = "档位分界与解锁件数，全部来自 2026-10-12 真实商城数据实算"
    S.append('<text x="24" y="58" font-size="12" fill="#8C8A82">%s</text>' % sub)
    if data["value_per_100"]:
        top = tiers[-1]["threshold"]
        val = top / data["best_rate"] if data["best_rate"] else 0
        S.append('<text x="24" y="76" font-size="12" fill="#8C8A82">'
                 '每 100 积分账面现值 ¥%.2f · %d 分 ≈ ¥%.1f'
                 '</text>' % (data["value_per_100"], top, val))

    # 横轴
    S.append('<line x1="%d" y1="%d" x2="%d" y2="%d" stroke="url(#axis)" '
             'stroke-width="3" stroke-linecap="round"/>'
             % (AXIS_X0, AXIS_Y, AXIS_X1, AXIS_Y))
    labels = ["0"] + [str(t["threshold"]) for t in tiers]
    for i, lab in enumerate(labels):
        x = x_of(i)
        S.append('<circle cx="%.1f" cy="%d" r="4.5" fill="%s"/>' % (x, AXIS_Y, C_YELLOW))
        S.append('<text x="%.1f" y="%d" font-size="12" fill="#8C8A82" '
                 'text-anchor="middle">%s</text>' % (x, AXIS_Y + 24, lab))
    S.append('<text x="24" y="%d" font-size="11" fill="#8C8A82">单位：积分</text>'
             % (AXIS_Y + 5))

    # 卡片（上下交错）
    for i, t in enumerate(tiers):
        x = x_of(i + 1)
        up = (i % 2 == 0)
        top = AXIS_Y - CARD_GAP_UP - CARD_H if up else AXIS_Y + CARD_GAP_DOWN
        left = x - CARD_W / 2
        S.append('<line x1="%.1f" y1="%d" x2="%.1f" y2="%d" stroke="#4A4858" '
                 'stroke-width="1.5"/>'
                 % (x, AXIS_Y, x, top + CARD_H if up else top))
        S.append('<rect x="%.1f" y="%d" width="%d" height="%d" rx="10" '
                 'fill="#262430" stroke="%s" stroke-opacity="0.45" stroke-width="1.5"/>'
                 % (left, top, CARD_W, CARD_H, C_YELLOW))
        lines = card_lines(t, data)
        ty = top + 24
        for text, size, color, bold in lines:
            S.append('<text x="%.1f" y="%d" font-size="%d" fill="%s"%s>%s</text>'
                     % (left + 12, ty, size, color,
                        ' font-weight="700"' if bold else '', text))
            ty += size + 7

    # 底部注释
    traps = data["traps"]
    foot_y = AXIS_Y + CARD_GAP_DOWN + CARD_H + 22
    if traps:
        n, ps = traps[0]
        S.append('<text x="24" y="%d" font-size="12" fill="%s">⚠ 同名不同分：'
                 '%s %s 分并存，掌柜会标出</text>'
                 % (foot_y, CORAL_HEX, strip_price(n),
                    " 与 ".join(str(p) for p in ps)))
    S.append('<text x="%d" y="%d" font-size="11" fill="#8C8A82" text-anchor="middle">'
             '麦享掌柜 mc-points-steward · 麦当劳中国 MCP 开发者创新大赛参赛作品</text>'
             % (W // 2, H - 10))
    S.append('</svg>')
    return "\n".join(S)


def card_lines(t, data):
    """卡片文字：[(text, size, hexcolor, bold)]。
    宽度约束：卡片可用 124px，12px 字号约 10 个全角字符——文案按此设计。
    件数信息在「解锁 N 件可兑」已给，行3 只展性价比最优的那一件。"""
    lines = []
    lines.append(("%d 分" % t["threshold"], 16, C_YELLOW, True))
    if t["is_lottery"]:
        lines.append(("解锁抽奖资格", 12, FG_HEX, False))
        lines.append(("%d分/次·%d品" % (t["threshold"], data["lottery"]["prize_count"]),
                      11, DIM_HEX, False))
        lines.append(("最高回血%d分" % data["lottery"]["max_back"], 11, DIM_HEX, False))
    else:
        lines.append(("解锁 %d 件可兑" % t["unlocked"], 12, FG_HEX, False))
        best = min(t["items"], key=lambda m: (m.get("unit_price") is None,
                                              m.get("unit_price") or 0))
        lines.append((strip_price(best["name"]), 11, FG_HEX, False))
        if t["cash_min"] is not None:
            lines.append(("另付¥%.1f起" % t["cash_min"], 11, CORAL_HEX, False))
    return lines


# ---------------------------------------------------------------- GIF
def _bezier(p0, p1, p2, p3, steps=16):
    pts = []
    for i in range(steps + 1):
        t = i / steps
        mt = 1 - t
        x = mt ** 3 * p0[0] + 3 * mt ** 2 * t * p1[0] + 3 * mt * t ** 2 * p2[0] + t ** 3 * p3[0]
        y = mt ** 3 * p0[1] + 3 * mt ** 2 * t * p1[1] + 3 * mt * t ** 2 * p2[1] + t ** 3 * p3[1]
        pts.append((x, y))
    return pts


def arch_points(scale=0.55):
    """金拱门 path 的贝塞尔采样点（GIF 用）。控制点与 ARCH_PATH 对应。"""
    segs = [((10, 92), (10, 22), (26, 10), (42, 10)),
            ((42, 10), (54, 10), (58, 24), (60, 50)),
            ((60, 50), (62, 24), (66, 10), (78, 10)),
            ((78, 10), (94, 10), (110, 22), (110, 92))]
    pts = []
    for s in segs:
        pts.extend(_bezier(*s))
    return [(W - 62 + p[0] * scale, 8 + p[1] * scale) for p in pts]


def find_font():
    for p in FONT_CANDIDATES:
        if os.path.isfile(p):
            return p
    return None


def gif_overflow(data, draw, fonts):
    """GIF 卡片文字超宽护栏。返回超宽 (tier, text, px) 列表。"""
    bad = []
    for t in data["tiers"]:
        for idx, (text, size, _, _) in enumerate(card_lines(t, data)):
            font = fonts[0] if idx == 0 else fonts[1]
            w = draw.textlength(text, font=font)
            if w > CARD_W - 24:
                bad.append((t["threshold"], text, int(w)))
    return bad


def render_frame(data, fonts, axis_progress, card_progress, title_len):
    """渲染一帧。axis_progress 0~1；card_progress: {tier_idx: 0~1}。"""
    from PIL import Image, ImageDraw
    f_title, f_big, f_card, f_note = fonts
    img = Image.new("RGB", (W, H), BG_RGB)
    d = ImageDraw.Draw(img)

    # 标题（打字机）
    title = "你有多少积分，掌柜就怎么答"
    if title_len:
        d.text((24, 12), title[:title_len], font=f_title, fill=YELLOW_RGB)

    # 金拱门（标题右侧，与 banner.svg 同 path 的贝塞尔采样）
    d.line(arch_points(), fill=YELLOW_RGB, width=9, joint="curve")

    # 副标题
    d.text((24, 50), "档位分界与解锁件数，全部来自 2026-10-12 真实商城数据实算",
           font=f_note, fill=DIM_RGB)
    if data["value_per_100"]:
        top = data["tiers"][-1]["threshold"]
        val = top / data["best_rate"] if data["best_rate"] else 0
        d.text((24, 68), "每 100 积分账面现值 ¥%.2f · %d 分 ≈ ¥%.1f"
               % (data["value_per_100"], top, val), font=f_note, fill=DIM_RGB)

    # 横轴（生长）
    n = len(data["tiers"])
    step = (AXIS_X1 - AXIS_X0) / n
    x_of = lambda i: AXIS_X0 + i * step  # noqa: E731
    cur_x = AXIS_X0 + (AXIS_X1 - AXIS_X0) * axis_progress
    d.line([(AXIS_X0, AXIS_Y), (cur_x, AXIS_Y)], fill=YELLOW_RGB, width=3)

    labels = ["0"] + [str(t["threshold"]) for t in data["tiers"]]
    for i, lab in enumerate(labels):
        x = x_of(i)
        if x > cur_x:
            continue
        d.ellipse([x - 4.5, AXIS_Y - 4.5, x + 4.5, AXIS_Y + 4.5], fill=YELLOW_RGB)
        lw = d.textlength(lab, font=f_note)
        d.text((x - lw / 2, AXIS_Y + 12), lab, font=f_note, fill=DIM_RGB)
    d.text((24, AXIS_Y - 6), "单位：积分", font=f_note, fill=DIM_RGB)

    # 卡片（上下交错，滑入）
    for i, t in enumerate(data["tiers"]):
        p = card_progress.get(i, 0)
        if p <= 0:
            continue
        x = x_of(i + 1)
        if x > cur_x:
            continue
        up = (i % 2 == 0)
        top = AXIS_Y - CARD_GAP_UP - CARD_H if up else AXIS_Y + CARD_GAP_DOWN
        left = x - CARD_W / 2
        # 连接线
        line_end = (top + CARD_H) if up else top
        d.line([(x, AXIS_Y), (x, line_end)], fill=(74, 72, 88), width=2)
        # 滑入偏移
        off = (1 - p) * 20
        ty = top + off
        d.rounded_rectangle([left, ty, left + CARD_W, ty + CARD_H], radius=10,
                            fill=CARD_RGB, outline=(200, 160, 60), width=2)
        ty_text = ty + 12
        for idx, (text, size, color, bold) in enumerate(card_lines(t, data)):
            d.text((left + 12, ty_text), text,
                   font=(f_big if idx == 0 else f_card), fill=rgb_of(color))
            ty_text += (16 if idx == 0 else 12) + 7

    # 底部注释
    traps = data["traps"]
    foot_y = AXIS_Y + CARD_GAP_DOWN + CARD_H + 22
    if traps:
        nm, ps = traps[0]
        d.text((24, foot_y), "⚠ 同名不同分：%s %s 分并存，掌柜会标出"
               % (strip_price(nm), " 与 ".join(str(p) for p in ps)),
               font=f_note, fill=CORAL_RGB)
    foot = "麦享掌柜 mc-points-steward · 麦当劳中国 MCP 开发者创新大赛参赛作品"
    fw = d.textlength(foot, font=f_note)
    d.text(((W - fw) / 2, H - 12), foot, font=f_note, fill=DIM_RGB)
    return img


def build_gif(data, out, scale=1.0):
    try:
        from PIL import Image, ImageDraw, ImageFont
    except ImportError:
        print("需要 Pillow：pip install Pillow")
        return 2

    font_path = find_font()
    if not font_path:
        print("找不到中文字体（试过 %s）" % ", ".join(FONT_CANDIDATES))
        return 2

    font = ImageFont.truetype(font_path, 15)
    fonts = (font,
             ImageFont.truetype(font_path, 16),
             ImageFont.truetype(font_path, 12),
             ImageFont.truetype(font_path, 12))

    probe = ImageDraw.Draw(Image.new("RGB", (8, 8)))
    bad = gif_overflow(data, probe, fonts)
    if bad:
        print("⚠️ %d 条卡片文字超出卡片宽度 %d，请精简文案或调 CARD_W：" % (len(bad), CARD_W))
        for th, text, px in bad:
            print("   [%d分档 %dpx] %s" % (th, px, text))
        return 3

    title = "你有多少积分，掌柜就怎么答"
    frames, durations = [], []

    def add(img, ms):
        frames.append(img)
        durations.append(ms)

    # 1) 标题打字机
    for i in range(1, len(title) + 1):
        add(render_frame(data, fonts, 0, {}, i), 62)

    # 2) 轴线生长
    for f in range(1, 25):
        add(render_frame(data, fonts, f / 24.0, {}, len(title)), 40)

    # 3) 卡片依次滑入
    n_tiers = len(data["tiers"])
    for i in range(n_tiers):
        prog = {}
        for f in range(1, 11):
            prog[i] = f / 10.0
            add(render_frame(data, fonts, 1.0, dict(prog), len(title)), 45)

    # 4) 停留
    for _ in range(14):
        add(render_frame(data, fonts, 1.0,
                         {i: 1.0 for i in range(n_tiers)}, len(title)), 220)

    if scale != 1.0:
        w2, h2 = int(W * scale), int(H * scale)
        frames = [f.resize((w2, h2)) for f in frames]

    os.makedirs(os.path.dirname(out), exist_ok=True)
    frames[0].save(out, save_all=True, append_images=frames[1:],
                   duration=durations, loop=0, optimize=True)
    print("已生成 %s（%d 帧，%.1f 秒，%d 字节）"
          % (out, len(frames), sum(durations) / 1000.0, os.path.getsize(out)))
    return 0


def main():
    ap = argparse.ArgumentParser(description="合成积分解锁天梯宣传物料")
    ap.add_argument("--out-gif", default=None, help="默认 <仓库根>/assets/points-ladder.gif")
    ap.add_argument("--out-svg", default=None, help="默认 <仓库根>/assets/points-ladder.svg")
    ap.add_argument("--scale", type=float, default=1.0, help="GIF 缩放，默认 1.0")
    ap.add_argument("--svg-only", action="store_true", help="只出 SVG（无需 Pillow）")
    args = ap.parse_args()

    data = compute()
    tiers = data["tiers"]
    if not tiers:
        print("tiers 为空，检查 fixtures")
        return 2

    out_svg = args.out_svg or os.path.join(ROOT, "assets", "points-ladder.svg")
    out_svg = os.path.abspath(out_svg)
    os.makedirs(os.path.dirname(out_svg), exist_ok=True)
    with open(out_svg, "w", encoding="utf-8") as f:
        f.write(build_svg(data) + "\n")
    print("已生成 %s（%d 字节）" % (out_svg, os.path.getsize(out_svg)))
    print("天梯 %d 级：%s" % (len(tiers),
          " / ".join("%d分(%s)" % (t["threshold"],
                                   "抽奖" if t["is_lottery"] else "%d件" % t["unlocked"])
                     for t in tiers)))
    if data["traps"]:
        print("同名陷阱 %d 组：%s" % (len(data["traps"]),
              "；".join("%s %s" % (n, ps) for n, ps in data["traps"])))

    if args.svg_only:
        return 0

    out_gif = args.out_gif or os.path.join(ROOT, "assets", "points-ladder.gif")
    return build_gif(data, os.path.abspath(out_gif), args.scale)


if __name__ == "__main__":
    sys.exit(main())
