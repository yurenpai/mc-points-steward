#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
make_banner_svg.py —— 生成「麦享掌柜」品牌横幅（README 首屏门面）

为什么需要它：
    榜单前 10 名几乎都有品牌横幅（第 1 名 banner.svg 用深棕底 + 麦当劳金拱门
    logo + 金色辉光）。品牌横幅是评委对作品的第一印象，也是「可截图分享」
    物料里传播效率最高的一张。本项目此前只有浅色报告卡，缺一张门面。

设计约束（与 make_report_svg.py 一致）：
    1. **数字零手抄** —— 三个 pill 的数值全部由 tests/fixtures 实算
       （classify / 默认查询 vs 逐类目对比），改数据必须重跑本脚本。
    2. 自包含单文件 SVG：金拱门为手绘 SVG path，不引外部图片/字体。
    3. 深棕底是刻意的——麦当劳品牌色里的「暖深棕」与金色 M 对比度最高，
       且与浅色报告卡形成「门面深 / 内容浅」的层次。

用法:
    python make_banner_svg.py                    # 输出到 <仓库根>/assets/banner.svg
    python make_banner_svg.py --out other.svg    # 指定输出路径
    python make_banner_svg.py --stdout           # 打到标准输出
"""

import argparse
import json
import os
import sys
from datetime import datetime

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from rank_products import classify, TIME_FMT  # noqa: E402

FIXTURES = os.path.join(os.path.dirname(HERE), "tests", "fixtures")

# 麦当劳品牌色
C_YELLOW = "#FFC72C"
C_YELLOW_DEEP = "#FF8A00"
C_RED = "#DA291C"
C_INK = "#FFFFFF"
C_SUB = "#F2E6D8"
C_MUTED = "#B8A88F"

W, H = 680, 300
M = 24


def esc(s):
    """XML 转义。商品名是官方字符串，必须转义后才能进 SVG。"""
    return (str(s).replace("&", "&amp;").replace("<", "&lt;")
            .replace(">", "&gt;").replace('"', "&quot;"))


def text(x, y, s, size, fill, weight=None, anchor=None, spacing=None, family=None):
    a = ['x="%d"' % x, 'y="%d"' % y, 'font-size="%s"' % size, 'fill="%s"' % fill]
    if weight:
        a.append('font-weight="%s"' % weight)
    if anchor:
        a.append('text-anchor="%s"' % anchor)
    if spacing:
        a.append('letter-spacing="%s"' % spacing)
    if family:
        a.append('font-family="%s"' % family)
    return "<text %s>%s</text>" % (" ".join(a), esc(s))


def load(name):
    with open(os.path.join(FIXTURES, name), "r", encoding="utf-8") as f:
        raw = json.load(f)
    return raw.get("data", raw)


def compute():
    """从 fixtures 实算三个核心指标（零手抄）。"""
    now = datetime.now()
    try:
        meta = json.load(open(os.path.join(FIXTURES, "_meta_20261012.json"),
                              encoding="utf-8"))
        now = datetime.strptime(meta.get("now", now.strftime(TIME_FMT)), TIME_FMT)
    except Exception:
        pass

    default = load("mall_products_20261012.json")
    cat = []
    for name in ("mall_products_cat_1_4_20261012.json",
                 "mall_products_cat_2_8_20261012.json"):
        cat.extend(load(name))

    pts = lambda L: [x for x in L if int(str(x.get("point", "0") or 0)) > 0]

    def buckets(L):
        b = {"redeemable": [], "extinct": []}
        for x in L:
            kind, _ = classify(x, now)
            if kind in b:
                b[kind].append(x)
        return b

    d_all, c_all = pts(default), pts(cat)
    d_b, c_b = buckets(d_all), buckets(c_all)

    # 假上架率：合并类目后的积分类商品中，名存实亡的占比
    total = len(d_all) + sum(1 for x in c_all
                             if x.get("spuId") not in {y["spuId"] for y in d_all})
    fake = len(c_b["extinct"])
    fake_rate = fake * 100.0 / total if total else 0.0

    # 纯积分白拿：真可兑里需要到店另付现金的件数
    # 复用 apply_detail 的提取逻辑（extTradePrice 藏在 skuList，勿自行解析）
    redeemable = c_b["redeemable"]
    metas = []
    for x in redeemable:
        kind, meta = classify(x, now)
        if kind != "redeemable":
            continue
        metas.append(meta)
    try:
        from rank_products import load_details, apply_detail
        det = load_details([os.path.join(FIXTURES, "mall_details_20261012.json")])
        for meta in metas:
            apply_detail(meta, det[meta.get("spuId")]) if meta.get("spuId") in det else None
    except Exception:
        pass
    cash_n = sum(1 for m in metas if m.get("cash_on_top"))

    # 默认查询漏报：合并后真可兑 - 默认查询真可兑
    missed = len(redeemable) - len(d_b["redeemable"])

    return {
        "total": total,
        "fake": fake,
        "fake_rate": fake_rate,
        "redeemable": len(redeemable),
        "cash_n": cash_n,
        "white_take": max(0, len(redeemable) - cash_n),
        "missed": max(0, missed),
    }


def build(m):
    S = []
    S.append('<svg viewBox="0 0 %d %d" width="100%%" xmlns="http://www.w3.org/2000/svg" '
             'role="img" font-family="-apple-system, BlinkMacSystemFont, \'Segoe UI\', '
             '\'PingFang SC\', \'Microsoft YaHei\', sans-serif">' % (W, H))
    S.append("<title>麦享掌柜 mc-points-steward — 麦当劳积分资产管家</title>")
    S.append("<desc>2026-10-12 麦当劳官方 MCP 实测：标称上架的积分类商品中 %d 件名存实亡"
             "（假上架率 %.0f%%）；%d 件真可兑中 %d 件需到店另付现金，纯积分白拿 %d 件；"
             "默认查询漏报 %d 件。</desc>"
             % (m["fake"], m["fake_rate"], m["redeemable"], m["cash_n"],
                m["white_take"], m["missed"]))
    S.append("<defs>")
    S.append('<linearGradient id="bg" x1="0" y1="0" x2="1" y2="1">'
             '<stop offset="0%" stop-color="#1a0d08"/>'
             '<stop offset="55%" stop-color="#2b1108"/>'
             '<stop offset="100%" stop-color="#140806"/></linearGradient>')
    S.append('<linearGradient id="gold" x1="0" y1="0" x2="1" y2="0">'
             '<stop offset="0%" stop-color="' + C_YELLOW + '"/>'
             '<stop offset="100%" stop-color="' + C_YELLOW_DEEP + '"/></linearGradient>')
    S.append('<filter id="glow" x="-40%" y="-40%" width="180%" height="180%">'
             '<feGaussianBlur in="SourceAlpha" stdDeviation="7" result="b"/>'
             '<feFlood flood-color="#FFB020" flood-opacity="0.5" result="c"/>'
             '<feComposite in="c" in2="b" operator="in" result="halo"/>'
             '<feMerge><feMergeNode in="halo"/><feMergeNode in="SourceGraphic"/>'
             '</feMerge></filter>')
    S.append("</defs>")

    # 背景 + 装饰光斑（避开文字区）
    S.append('<rect width="%d" height="%d" fill="url(#bg)"/>' % (W, H))
    S.append('<circle cx="30" cy="%d" r="150" fill="%s" opacity="0.07"/>' % (H, C_YELLOW))
    S.append('<circle cx="%d" cy="24" r="170" fill="%s" opacity="0.12"/>' % (W, C_RED))

    # 左：金拱门 M（手绘 path，粗圆头笔画）
    S.append('<g filter="url(#glow)" transform="translate(46,68) scale(0.86)">')
    S.append('<path d="M 10 92 C 10 22 26 10 42 10 C 54 10 58 24 60 50 '
             'C 62 24 66 10 78 10 C 94 10 110 22 110 92" fill="none" '
             'stroke="%s" stroke-width="16" stroke-linecap="round" '
             'stroke-linejoin="round"/>' % C_YELLOW)
    S.append("</g>")

    # 右：文字列
    tx = 190
    S.append(text(tx, 92, "麦享掌柜", 40, C_INK, weight="700", spacing="4"))
    S.append(text(tx + 2, 118, "mc-points-steward", 14, C_YELLOW, spacing="1.5",
                  family="'Menlo','Consolas',monospace"))
    S.append('<rect x="%d" y="132" width="120" height="3.5" rx="1.75" fill="url(#gold)"/>'
             % (tx + 2))
    S.append(text(tx, 160, "别的工具帮你点这一单，", 15, C_SUB))
    S.append(text(tx, 182, "我们帮你守住积分资产。", 15, C_SUB))
    S.append(text(tx, 206, "麦当劳中国 MCP 开发者创新大赛 · 参赛作品", 10.5, C_MUTED,
                  spacing="1"))

    # 底：三个数据 pill（数值实算）
    pills = [
        ("%d%%" % round(m["fake_rate"]), "假上架率", m["fake"], "件名存实亡"),
        ("%d 件" % m["white_take"], "纯积分白拿", m["cash_n"], "件需到店另付"),
        ("%d 件" % m["missed"], "默认查询漏报", m["total"], "件标称上架"),
    ]
    pw = (W - 2 * M - 2 * 12) // 3
    py, ph = 230, 48
    for i, (big, label, sub_n, sub_label) in enumerate(pills):
        px = M + i * (pw + 12)
        S.append('<rect x="%d" y="%d" width="%d" height="%d" rx="10" '
                 'fill="#FFFFFF" fill-opacity="0.06" stroke="%s" stroke-opacity="0.28"/>'
                 % (px, py, pw, ph, C_YELLOW))
        S.append(text(px + 14, py + 22, big, 19, C_YELLOW, weight="700"))
        S.append(text(px + 14, py + 39, label, 10, C_SUB))
        S.append(text(px + pw - 14, py + 22, "%s %d" % ("·", sub_n), 11, C_MUTED,
                      anchor="end"))
        S.append(text(px + pw - 14, py + 38, sub_label, 9.5, C_MUTED, anchor="end"))

    S.append("</svg>")
    return "\n".join(S)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=None)
    ap.add_argument("--stdout", action="store_true")
    args = ap.parse_args()

    m = compute()
    svg = build(m)
    if args.stdout:
        print(svg)
        return 0
    out = args.out or os.path.join(os.path.dirname(os.path.dirname(HERE)),
                                   "assets", "banner.svg")
    os.makedirs(os.path.dirname(out), exist_ok=True)
    with open(out, "w", encoding="utf-8") as f:
        f.write(svg + "\n")
    print("已生成 %s（%d 字节）" % (out, len(svg.encode("utf-8"))))
    print("  假上架率 %.0f%%（%d/%d） · 纯积分白拿 %d 件（另付 %d 件） · 漏报 %d 件"
          % (m["fake_rate"], m["fake"], m["total"], m["white_take"],
             m["cash_n"], m["missed"]))
    return 0


if __name__ == "__main__":
    sys.exit(main())
