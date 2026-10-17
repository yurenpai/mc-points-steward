#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
demo.py —— 麦享掌柜 · 离线演示模式（Offline Demo）

为什么需要它：
    本 Skill 依赖麦当劳 MCP（需账号 Token）。评审者与访客大多没有 Token，
    连不上 MCP 时 Skill 什么都跑不出来 —— 作品等于无法验证。
    本脚本用仓库内的真实数据快照（tests/fixtures/，2026-10-12 真实调用，
    accountId 已脱敏）复现完整输出效果，让无 Token 环境也能验证作品。

与运行时脚本的区别（重要，勿混淆）：
    rank_products.py / lottery_advice.py 是 **Skill 运行时依赖** ——
    只做确定性计算，绝不输出主观判断（见规划 5.4）。
    demo.py 是 **演示工具**，输出的是模板实例化后的成品样式，
    不参与 Skill 实际运行。

用法:
    python demo.py                  # 完整三段演示
    python demo.py --section 2      # 单看一段：1 积分账本 / 2 兑换榜单 / 3 抽奖参谋

数据来源: tests/fixtures/*_20261012.json（真实调用快照，非编造）
"""

import argparse
import json
import os
import sys
from datetime import datetime

HERE = os.path.dirname(os.path.abspath(__file__))
FIXTURES = os.path.join(os.path.dirname(HERE), "tests", "fixtures")

# 复用运行时脚本的判定逻辑，确保「演示结果」与「真实运行」行为完全一致
sys.path.insert(0, HERE)
from rank_products import (  # noqa: E402
    classify, parse_time, TIME_FMT, load_details, apply_detail, points_value,
)

W = 34  # 横幅宽度（半角字符数）


def pad(s, n):
    """按终端显示宽度左对齐补空格（中文按 2 列计）"""
    s = str(s)
    width = sum(2 if ord(c) > 127 else 1 for c in s)
    return s + " " * max(0, n - width)


def banner(title):
    line = "─" * W
    return "%s\n  %s\n%s" % (line, title, line)


def sub(label):
    """小节分隔：  ── 来龙去脉 ──────────────"""
    head = "── %s " % label
    return "  " + head + "─" * max(0, W - len(head) - 1)


def row(label, value, unit=" 分", width=14):
    return "  %s%s%s" % (pad(label, width), value, unit)


def load(name):
    with open(os.path.join(FIXTURES, name), "r", encoding="utf-8") as f:
        raw = json.load(f)
    return raw.get("data", raw), raw.get("_meta", {})


# 积分类目：逐类目查询的真实快照（默认查询会漏商品，见 SKILL.md 数据陷阱第 8 条）
CAT_FIXTURES = [
    "mall_products_cat_1_4_20261012.json",   # 商品券 1>4
    "mall_products_cat_2_8_20261012.json",   # 周边产品 2>8
]
DEFAULT_QUERY_FIXTURE = "mall_products_20261012.json"   # 不传 catRuleIds 的默认查询


def load_mall():
    """按 spuId 合并各类目快照；返回 (商品列表, 覆盖率信息)。"""
    merged, coverage = {}, []
    for name in CAT_FIXTURES:
        items, _ = load(name)
        items = items if isinstance(items, list) else items.get("data", items)
        for it in items:
            sid = it.get("spuId")
            if sid is not None:
                merged.setdefault(sid, it)
        coverage.append((name, len(items)))
    return list(merged.values()), coverage


def _default_query_items():
    try:
        items, _ = load(DEFAULT_QUERY_FIXTURE)
        items = items if isinstance(items, list) else items.get("data", items)
        return items if isinstance(items, list) else []
    except Exception:
        return []


def default_query_ids():
    """默认查询（不传 catRuleIds）返回的商品 id 集合，用于算漏报。"""
    return set(i.get("spuId") for i in _default_query_items())


def default_cash_count():
    """默认查询里的现金商品件数（积分类目快照不含它们）。"""
    n = 0
    for it in _default_query_items():
        try:
            point = int(str(it.get("point", "")).strip() or "0")
            price = float(str(it.get("price", "0")).strip() or 0)
        except (TypeError, ValueError):
            continue
        if point == 0 and price > 0:
            n += 1
    return n


DETAIL_FIXTURE = "mall_details_20261012.json"   # 真可兑 9 件详情（补出隐藏现金成本）


def load_mall_details():
    """加载详情快照。列表接口没有 extTradePrice，只能从这里补。"""
    try:
        return load_details([os.path.join(FIXTURES, DETAIL_FIXTURE)])
    except Exception:
        return {}


def _best_rate_info():
    """算最优出口汇率与每 100 积分现值（与 W2 同源，避免两处数字打架）。
    账户即使 0 分，这个汇率也有信息量——它回答「攒够 100 分值多少钱」。"""
    try:
        items, _ = load_mall()
        items = items if isinstance(items, list) else items.get("data", items)
        now = datetime.now()
        details = load_mall_details()
        redeemable = []
        for it in items:
            b, m = classify(it, now)
            if b != "redeemable":
                continue
            d = details.get(it.get("spuId"))
            if d:
                apply_detail(m, d)
            redeemable.append(m)
        return points_value(redeemable, None)
    except Exception:
        return None


# ---------------------------------------------------------------- W1
def sec_account():
    d, meta = load("account_20261012.json")
    L = [banner("麦享掌柜 · 积分账本（W1）")]
    L.append(row("可用积分", d.get("availablePoint", "-")))
    L.append(sub("来龙去脉"))
    L.append(row("累计获得", d.get("accumulativePoint", "-")))
    L.append(row("已使用", d.get("usedPoint", "-")))
    L.append(row("已过期", d.get("expiredPoint", "-")))
    L.append(row("冻结中", d.get("frozenPoint", "-")))
    L.append(sub("到期提醒"))
    L.append(row("本月将过期", d.get("currentMouthExpirePoint", "-")))
    L.append(row("下月将过期", d.get("nextMouthExpirePoint", "-")))
    L.append(row("上月已过期", d.get("lastMouthExpirePoint", "-")))
    L.append("─" * W)

    avail = int(d.get("availablePoint", 0) or 0)
    if avail == 0:
        L.append("  掌柜批注")
        L.append("  账上是空的。这不要紧——眼下商城")
        L.append("  真能兑的有 %s 件（见下一段），攒够就开张。" % _redeemable_count())
        L.append("")
        L.append("  三条攒分路子（客观列出，不催你）：")
        L.append("   ① 消费累积 —— 每笔订单自动计分")
        L.append("   ② 抽奖回血 —— 24 分/次，奖池含")
        L.append("      「30 积分」，理论上能滚起来")
        L.append("   ③ 活动赠送 —— 麦金学期卡学生")
        L.append("      49 元/150 天，赠多邻国月卡")
    else:
        cur = int(d.get("currentMouthExpirePoint", 0) or 0)
        nxt = int(d.get("nextMouthExpirePoint", 0) or 0)
        if cur or nxt:
            L.append("  ⚠️ 掌柜提醒：有积分即将到期，优先处置。")
        else:
            L.append("  掌柜批注：账上有 %s 分，暂无到期压力。" % avail)
    L.append("─" * W)

    # 资产现值：积分是资产，该有账面价值（口径见 rank_products.points_value）
    pv = _best_rate_info()
    if pv:
        L.append(sub("资产现值"))
        L.append("  按最优出口折算（%s，%s 分）：" % (pv["best_exit"][:20], pv["best_exit_point"]))
        L.append("  %s¥%.2f" % (pad("每 100 积分现值", 16), pv["value_per_100"]))
        if pv["total_value"] is not None:
            L.append("  %s¥%.2f" % (pad("你账上 %s 分现值" % pv["point"], 16), pv["total_value"]))
        L.append("  ⚠️ 但每件都要到店另付现金（见下一段）")
        L.append("─" * W)
    L.append("  账户 %s · %s" % (d.get("accountId", "-"), d.get("currency", "-")))
    return "\n".join(L)


def _redeemable_count():
    """供 W1 提示语使用：真可兑件数（与 W2 同源，避免两处数字打架）"""
    try:
        items, _ = load_mall()
        now = datetime.now()
        return sum(1 for it in items if classify(it, now)[0] == "redeemable")
    except Exception:
        return "若干"


# ---------------------------------------------------------------- W2
def sec_mall():
    items, coverage = load_mall()
    items = items if isinstance(items, list) else items.get("data", items)
    now = datetime.now()

    details = load_mall_details()
    buckets = {"redeemable": [], "extinct": [], "cash_only": [], "unknown_expiry": []}
    for it in items:
        b, m = classify(it, now)
        d = details.get(it.get("spuId"))
        if d:
            apply_detail(m, d)
        buckets[b].append(m)
    buckets["redeemable"].sort(
        key=lambda x: (x["unit_price"] is None, x["unit_price"] or 0, x["point"])
    )
    buckets["extinct"].sort(key=lambda x: -x["point"])

    # 可用积分（用于"还差多少"提示）
    try:
        acct, _ = load("account_20261012.json")
        avail = int(acct.get("availablePoint", 0) or 0)
    except Exception:
        avail = 0

    # 同名商品检测：不同 spuId 但同名，积分可能差一倍（实测存在此类陷阱）
    by_name = {}
    for r in buckets["redeemable"]:
        by_name.setdefault(r["name"], []).append(r)

    dup_groups = {k: v for k, v in by_name.items() if len(v) > 1}

    L = [banner("积分商城 · 真实可兑榜单（W2）")]
    L.append("  %s 件在售 → 去伪后 %s 件真可兑" % (len(items), len(buckets["redeemable"])))

    # 类目补全：默认查询会漏商品，这里显式报告补回了什么
    missed = [it for it in buckets["redeemable"] if it["spuId"] not in default_query_ids()]
    if missed:
        L.append("  ⚠️ 默认查询漏报 %s 件，已按类目补回：" % len(missed))
        for r in missed:
            L.append("     + %s  %s 分" % (pad(r["name"][:20], 22), r["point"]))
    L.append("")

    cur_rarity = None
    for r in buckets["redeemable"]:
        if r["rarity"] != cur_rarity:
            cur_rarity = r["rarity"]
            L.append("  %s %s" % (r["icon"], cur_rarity))
        price = ("%s 分/元" % r["unit_price"]) if r["unit_price"] else "券面价未知"

        # 同名标记（实测为「同名不同物」，不再是「谁更贵」）
        dup = " ⚠️同名" if r["name"] in dup_groups else ""

        L.append("  %s %s分 %s%s" % (pad(r["name"][:20], 22), r["point"], price, dup))

        if r.get("drop_flag"):
            tail = "%s 限时掉落 · 剩 %s 天" % (r["drop_flag"], r["days_left"])
        else:
            tail = "%s 下架" % (r["downTime"] or "时间未知")
        gap = r["point"] - avail
        tail += " · %s" % ("✅ 可兑" if gap <= 0 else "还差 %s 分" % gap)
        if r.get("cash_on_top") is not None:
            tail += " · 到店另付 ¥%s" % r["cash_on_top"]
        L.append("       └ %s" % tail)

    # 隐藏现金成本：列表接口看不到，只有详情能补出
    priced = [r for r in buckets["redeemable"] if r.get("cash_on_top") is not None]
    if priced:
        pure = [r for r in priced if r["cash_on_top"] == 0]
        L.append("")
        L.append(sub("隐藏现金成本"))
        L.append("  🔴 真可兑 %s 件 → %s 件需到店另付现金，纯积分白拿 %s 件"
                 % (len(priced), len(priced) - len(pure), len(pure)))
        L.append("     另付区间 ¥%s ~ ¥%s" % (
            min(r["cash_on_top"] for r in priced),
            max(r["cash_on_top"] for r in priced)))
        L.append("     这笔钱不在列表接口里（extTradePrice 只在详情中），")
        L.append("     只看列表就推荐 = 告诉用户「100 分白拿冰淇淋」，其实是 100 分 + 3.9 元。")

    if dup_groups:
        L.append("")
        L.append(sub("同名陷阱 %s 组" % len(dup_groups)))
        for name, group in dup_groups.items():
            L.append("  ⚠️ %s" % name[:22])
            for s in sorted(group, key=lambda x: x["point"]):
                c = details.get(s["spuId"], {}).get("_contents") or "（内容见购买须知）"
                L.append("     %s 分 · 另付 ¥%s · %s" % (
                    s["point"],
                    s["cash_on_top"] if s.get("cash_on_top") is not None else "?",
                    c))
            L.append("     → 同名不同物，不是谁更贵的问题，按想吃什么选")

    L.append("")
    L.append(sub("已剔除 %s 件" % (len(items) - len(buckets["redeemable"]))))
    L.append("  名存实亡 %s 件（标 status=2 上架，实则已过期）" % len(buckets["extinct"]))
    for r in buckets["extinct"][:3]:
        L.append("    ☠️ %s  %s 分" % (pad(r["name"][:22], 24), r["point"]))
        L.append("       下架于 %s" % (r["downTime"] or "—"))
    if len(buckets["extinct"]) > 3:
        L.append("    …… 其余 %s 件见图鉴 · 绝版栏" % (len(buckets["extinct"]) - 3))
    cash_here = len(buckets["cash_only"])
    cash_default = default_cash_count()
    if cash_here == 0 and cash_default:
        L.append("  现金商品 本段未含（默认查询另有 %s 件，派对/品鉴会/体验营）" % cash_default)
    else:
        L.append("  现金商品 %s 件（point=0，派对/品鉴会/体验营）" % cash_here)
    if buckets["unknown_expiry"]:
        L.append("  时效未知 %s 件（缺 downTime，不臆断）" % len(buckets["unknown_expiry"]))

    L.append("─" * W)
    total = len(buckets["redeemable"]) + len(buckets["extinct"])
    L.append("  图鉴进度   金拱门限定 0 / %s" % len(buckets["redeemable"]))
    L.append("  已绝版收藏 %s 件" % len(buckets["extinct"]))
    drops = [r for r in buckets["redeemable"] if r.get("is_limited_drop")]
    if drops:
        L.append("  限时掉落   %s 件 %s" % (len(drops), drops[0]["drop_flag"]))
    else:
        L.append("  限时掉落   当前无")
    L.append("─" * W)
    L.append("  注：券面价由商品名解析（price 恒为 0，不是市价）")
    return "\n".join(L)


# ---------------------------------------------------------------- W3
def sec_lottery():
    d, meta = load("lottery_info_20261012.json")
    dec = d.get("drawDecision", {}) or {}
    prizes = d.get("prizes", []) or []

    L = [banner("积分抽奖 · 参谋（W3）")]
    L.append("  %s" % d.get("activityName", "—"))
    L.append("  状态 %s · 至 %s" % (d.get("activityStatusText", "—"),
                                    (d.get("endTime") or "—")[:10]))
    L.append("  单次消耗 %s 积分 · 你的可用 %s 分" % (
        d.get("drawPoint", "—"), d.get("availablePoint", "—")))
    L.append("")
    L.append(sub("奖池 %s 品" % len(prizes)))
    for p in prizes:
        L.append("    · %s  [%s]" % (pad(p.get("name", "—"), 22), p.get("typeText", "—")))
    L.append("")
    L.append(sub("资格判定"))
    eligible = dec.get("resourceEligible")
    if eligible:
        L.append("  ✅ 可以抽。%s" % (dec.get("nextConsumption", {}) or {}).get("text", ""))
    else:
        L.append("  ⛔ 暂不可抽 —— %s" % dec.get("reason", "原因未知"))
        L.append("  （资格只信 drawDecision，不由积分余额自行推断）")
    L.append("─" * W)
    L.append("  掌柜批注：奖池 10 品中仅 1 品为积分（30 积分），")
    L.append("  其余 9 品为优惠券。24 分换 30 分是唯一「回血」路径，")
    L.append("  但命中率未知——是否要抽，你拍板。")
    return "\n".join(L)


# ---------------------------------------------------------------- main
def main():
    ap = argparse.ArgumentParser(description="麦享掌柜 · 离线演示模式")
    ap.add_argument("--section", type=int, choices=[1, 2, 3], default=None,
                    help="只看某一段：1 积分账本 / 2 兑换榜单 / 3 抽奖参谋")
    args = ap.parse_args()

    if not os.path.isdir(FIXTURES):
        print("找不到 fixtures 目录：%s" % FIXTURES)
        return 2

    print()
    print("╔" + "═" * W + "╗")
    print("║" + pad("  |\\/|  麦享掌柜", W) + "║")
    print("║" + pad("  |/\\|  积分资产管家", W) + "║")
    print("╚" + "═" * W + "╝")
    print("  本演示使用仓库内数据快照（2026-10-12 真实调用），")
    print("  无需麦当劳 MCP Token 即可复现 Skill 的完整输出效果。")
    print("  账户 ID 已脱敏。实际使用时请连接 mcd-mcp 获取实时数据。")
    print()

    sections = {1: sec_account, 2: sec_mall, 3: sec_lottery}
    order = [args.section] if args.section else [1, 2, 3]
    for i in order:
        print(sections[i]())
        print()

    print("─" * W)
    print("  数据来源 tests/fixtures/：account_20261012.json ·")
    print("  mall_products_cat_1_4_20261012.json ·")
    print("  mall_products_cat_2_8_20261012.json ·")
    print("  mall_products_20261012.json（默认查询，用于对比漏报）·")
    print("  lottery_info_20261012.json")
    print("─" * W)
    return 0


if __name__ == "__main__":
    sys.exit(main())
