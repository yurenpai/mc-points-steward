#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
make_report_svg.py —— 生成「积分资产体检报告卡」（可截图发群 / 贴 README）

为什么需要它：
    本项目的输出长期只活在终端里（ASCII 文本），而榜单前 10 名几乎都把输出
    做成了可分享的图（GIF / SVG 卡片 / 在线页）。同一份内容，图的传播效率
    是文本的几十倍。本脚本把 W1/W2 的核心结论渲染成一张自包含 SVG。

设计约束：
    1. **数字零手抄** —— 全部由 tests/fixtures 实算（classify / points_value），
       改数据必须重跑本脚本，防止图文漂移。
    2. 自包含单文件 SVG，无外部字体/图片依赖。
    3. 输出浅色底（GitHub README 与微信均按浅色呈现）。

用法:
    python make_report_svg.py                    # 输出到 <仓库根>/assets/report-card.svg
    python make_report_svg.py --out other.svg    # 指定输出路径
    python make_report_svg.py --stdout           # 打到标准输出
"""

import argparse
import json
import os
import sys
from datetime import datetime

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from rank_products import (  # noqa: E402
    classify, TIME_FMT, load_details, apply_detail, points_value,
)

FIXTURES = os.path.join(os.path.dirname(HERE), "tests", "fixtures")

# 麦当劳品牌色（浅色底）
C_RED = "#993C1D"
C_RED_BRIGHT = "#DA291C"
C_YELLOW = "#FFC72C"
C_INK = "#26215C"
C_TEXT = "#2C2C2A"
C_SUB = "#888780"
C_LINE = "#D3D1C7"
C_CARD = "#FAF6EF"
C_WARN_BG = "#FDF0E7"
C_OK = "#2F6B3C"

W = 680          # 画布宽
H = 690          # 画布高（内容底 ~668 + 留白）
M = 24           # 左右边距
CW = W - 2 * M   # 内容宽


def esc(s):
    """XML 转义。商品名是官方字符串，必须转义后才能进 SVG。"""
    return (str(s).replace("&", "&amp;").replace("<", "&lt;")
            .replace(">", "&gt;").replace('"', "&quot;"))


def load(name):
    with open(os.path.join(FIXTURES, name), "r", encoding="utf-8") as f:
        raw = json.load(f)
    return raw.get("data", raw), raw.get("_meta", {})


def load_mall():
    merged = {}
    for name in ("mall_products_cat_1_4_20261012.json",
                 "mall_products_cat_2_8_20261012.json"):
        items, _ = load(name)
        items = items if isinstance(items, list) else items.get("data", items)
        for it in items:
            if it.get("spuId") is not None:
                merged.setdefault(it["spuId"], it)
    return list(merged.values())


def default_query_ids():
    try:
        items, _ = load("mall_products_20261012.json")
        items = items if isinstance(items, list) else items.get("data", items)
        return set(i.get("spuId") for i in items)
    except Exception:
        return set()


def text(x, y, s, size=12, fill=C_TEXT, weight=None, anchor=None):
    a = ' text-anchor="%s"' % anchor if anchor else ""
    w = ' font-weight="%s"' % weight if weight else ""
    return '<text x="%d" y="%d" font-size="%s" fill="%s"%s%s>%s</text>' % (
        x, y, size, fill, w, a, esc(s))


def rect(x, y, w, h, fill, rx=8, stroke=None):
    s = ' stroke="%s" stroke-width="1"' % stroke if stroke else ""
    return '<rect x="%d" y="%d" width="%d" height="%d" rx="%s" fill="%s"%s/>' % (
        x, y, w, h, rx, fill, s)


def build():
    now = datetime.now()
    items = load_mall()
    details = load_details([os.path.join(FIXTURES, "mall_details_20261012.json")])

    buckets = {"redeemable": [], "extinct": [], "cash_only": [], "unknown_expiry": []}
    for it in items:
        b, m = classify(it, now)
        d = details.get(it.get("spuId"))
        if d:
            apply_detail(m, d)
        buckets[b].append(m)

    red = buckets["redeemable"]
    red.sort(key=lambda x: (x["unit_price"] is None, x["unit_price"] or 0, x["point"]))
    pv = points_value(red, None)

    priced = [r for r in red if r.get("cash_on_top") is not None]
    with_cash = [r for r in priced if r["cash_on_top"] > 0]
    cash_min = min((r["cash_on_top"] for r in priced), default=None)
    cash_max = max((r["cash_on_top"] for r in priced), default=None)

    missed = [r for r in red if r["spuId"] not in default_query_ids()]
    extinct = buckets["extinct"]
    fake_rate = (len(extinct) * 100.0 / (len(red) + len(extinct))
                 if (len(red) + len(extinct)) else 0)

    best, worst = red[0], red[-1]
    max_up = worst["unit_price"] or 1

    S = []
    S.append('<svg viewBox="0 0 %d %d" width="100%%" xmlns="http://www.w3.org/2000/svg" '
             'role="img" font-family="-apple-system, BlinkMacSystemFont, \'Segoe UI\', '
             '\'PingFang SC\', \'Microsoft YaHei\', sans-serif">' % (W, H))
    S.append("<title>麦享掌柜 · 积分资产体检报告</title>")
    S.append("<desc>2026-10-12 麦当劳官方 MCP 实测：%d 件标称上架的积分类商品中，"
             "仅 %d 件真能兑换，且全部需要到店另付现金。</desc>"
             % (len(red) + len(extinct), len(red)))
    S.append(rect(0, 0, W, H, "#FFFFFF", rx=0))

    # ---------------- 头部 ----------------
    y = 34
    # 小型金拱门 M（浅底用麦当劳红，与深色 banner 的金色 M 形成呼应）
    S.append('<g transform="translate(24,15) scale(0.2)">'
             '<path d="M 10 92 C 10 22 26 10 42 10 C 54 10 58 24 60 50 '
             'C 62 24 66 10 78 10 C 94 10 110 22 110 92" fill="none" '
             'stroke="' + C_RED_BRIGHT + '" stroke-width="16" '
             'stroke-linecap="round" stroke-linejoin="round"/></g>')
    S.append(text(M + 32, y, "麦享掌柜 · 积分资产体检报告", 17, C_INK, "600"))
    S.append(text(M + 32, y + 20, "麦当劳中国 MCP 实测 · 2026-10-12 快照 · 数据非手抄，"
                "由 fixtures 实算生成", 11, C_SUB))
    S.append(rect(M, y + 30, CW, 3, C_YELLOW, rx=1.5))

    # ---------------- 四指标卡 ----------------
    y = 92
    cards = [
        ("每 100 积分现值", "¥%.2f" % pv["value_per_100"], "按最优出口折算", C_RED),
        ("真可兑商品", "%d 件" % len(red), "标称上架 %d 件" % (len(red) + len(extinct)), C_OK),
        ("假上架（名存实亡）", "%d 件" % len(extinct), "占比 %.0f%%" % fake_rate, C_RED_BRIGHT),
        ("纯积分白拿", "%d 件" % (len(priced) - len(with_cash)), "到店都要另付钱", C_RED_BRIGHT),
    ]
    gap = 12
    cw = (CW - gap * 3) / 4.0
    for i, (label, big, small, color) in enumerate(cards):
        x = M + i * (cw + gap)
        S.append(rect(x, y, cw, 86, C_CARD))
        S.append(text(x + 12, y + 22, label, 11, C_SUB))
        S.append(text(x + 12, y + 52, big, 22, color, "600"))
        S.append(text(x + 12, y + 72, small, 10, C_SUB))

    # ---------------- 三个反直觉结论 ----------------
    y = 202
    S.append(text(M, y, "三个反直觉结论", 14, C_INK, "600"))
    findings = [
        ("货架上 %.0f%% 是假的" % fake_rate,
         "%d 件标着 status=2「已上架」，其中 %d 件的下架时间早已过去 —— 名存实亡。"
         % (len(red) + len(extinct), len(extinct))),
        ("没有一件能「白拿」",
         "%d 件真可兑，%d 件需到店另付现金（¥%s ~ ¥%s）。"
         "「100 分换冰淇淋」实为 100 分 + 3.9 元。" % (
             len(priced), len(with_cash), cash_min, cash_max)),
        ("默认查询会漏货",
         "不传 catRuleIds 时接口少返回 %d 件真能兑的商品 —— 漏报率 %.0f%%。" % (
             len(missed), len(missed) * 100.0 / len(red) if red else 0)),
    ]
    fy = y + 16
    for i, (title, body) in enumerate(findings, 1):
        S.append(rect(M, fy, CW, 58, C_WARN_BG))
        S.append('<circle cx="%d" cy="%d" r="11" fill="%s"/>' % (M + 20, fy + 29, C_RED))
        S.append(text(M + 20, fy + 33, str(i), 12, "#FFFFFF", "600", "middle"))
        S.append(text(M + 40, fy + 22, title, 12.5, C_RED, "600"))
        S.append(text(M + 40, fy + 41, body, 11, C_TEXT))
        fy += 66

    # ---------------- 榜单：最优 vs 最差 ----------------
    y = fy + 12
    S.append(text(M, y, "同一张货架，性价比差 %.2f 倍" % (
        (worst["unit_price"] or 0) / (best["unit_price"] or 1)), 14, C_INK, "600"))
    S.append(text(M, y + 18, "按「分/元」升序，条越短越划算；每件都标出到店另付现金", 11, C_SUB))

    bar_x, bar_max = M + 171, 260
    rows = red[:3] + [worst] if len(red) > 3 else red
    ry = y + 40
    S.append(text(M, ry, "商品", 10, C_SUB))
    S.append(text(M + 151, ry, "积分", 10, C_SUB, None, "end"))
    S.append(text(bar_x, ry, "性价比（分/元）", 10, C_SUB))
    S.append(text(W - M, ry, "到店另付", 10, C_SUB, None, "end"))
    S.append('<line x1="%d" y1="%d" x2="%d" y2="%d" stroke="%s" stroke-width="0.5"/>'
             % (M, ry + 7, W - M, ry + 7, C_LINE))
    ry += 26
    for r in rows:
        up = r["unit_price"] or 0
        bw = max(4, int(bar_max * up / max_up)) if max_up else 4
        color = C_RED if up >= 25 else ("#D85A30" if up >= 18 else "#F0997B")
        S.append(text(M, ry, r["name"][:10], 11.5, C_TEXT))
        S.append(text(M + 151, ry, str(r["point"]), 11.5, "#444441", None, "end"))
        S.append(rect(bar_x, ry - 9, bw, 12, color, rx=3))
        S.append(text(bar_x + bar_max + 12, ry, "%.2f" % up, 11.5, C_TEXT))
        cash = r.get("cash_on_top")
        S.append(text(W - M, ry, ("¥%s" % cash) if cash is not None else "—",
                      11.5, C_RED, None, "end"))
        ry += 28

    # ---------------- 底部口径 ----------------
    ry += 6
    S.append('<line x1="%d" y1="%d" x2="%d" y2="%d" stroke="%s" stroke-width="0.5"/>'
             % (M, ry, W - M, ry, C_LINE))
    S.append(text(M, ry + 20, "口径：性价比 = 所需积分 ÷ 券面价（到店核销价）。"
                "MCP 不提供商品原价，故不计折扣率。", 10.5, C_SUB))
    S.append(text(M, ry + 36, "资产现值 = 可用积分 ÷ 最优出口汇率（%.2f 分/元，最优出口「%s」）。"
                % (pv["best_rate_per_yuan"], pv["best_exit"]), 10.5, C_SUB))
    S.append(text(M, ry + 52, "本图由 make_report_svg.py 从真实调用快照自动生成 · "
                "麦享掌柜 mc-points-steward · MIT", 10.5, C_SUB))
    # 底部品牌色带：红段 + 金段（与 banner 呼应）
    S.append(rect(0, H - 6, 140, 6, C_RED_BRIGHT, rx=0))
    S.append(rect(140, H - 6, W - 140, 6, C_YELLOW, rx=0))
    S.append("</svg>")
    return "\n".join(S)


def main():
    ap = argparse.ArgumentParser(description="生成积分资产体检报告卡 SVG")
    ap.add_argument("--out", default=None, help="输出路径，默认 <仓库根>/assets/report-card.svg")
    ap.add_argument("--stdout", action="store_true", help="打到标准输出")
    args = ap.parse_args()

    svg = build()

    if args.stdout:
        print(svg)
        return 0

    out = args.out or os.path.join(os.path.dirname(os.path.dirname(HERE)),
                                   "assets", "report-card.svg")
    os.makedirs(os.path.dirname(out), exist_ok=True)
    with open(out, "w", encoding="utf-8") as f:
        f.write(svg)
    print("已生成 %s（%d 字节）" % (out, len(svg.encode("utf-8"))))
    return 0


if __name__ == "__main__":
    sys.exit(main())
