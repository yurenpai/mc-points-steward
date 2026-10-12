#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
rank_products.py —— 积分商城「去伪 + 性价比排序」

设计原则（见开发规划 5.4 / 5.5）：
  本脚本只做确定性计算（过滤 / 排序 / 格式化），
  任何"建议""结论"一律由 Agent 生成，脚本绝不输出主观判断。

用法:
    python rank_products.py --input raw.json [--now "2026-10-12 14:55:00"]
    python rank_products.py --input a.json --input b.json   # 逐类目查询后合并
    python rank_products.py --input a.json --detail d.json  # 合并详情，补出隐藏现金成本

输入: mall-points-products 的原始返回（含 data 数组，或裸数组）
      可传多个 --input，按 spuId 去重合并。
      ⚠️ 实测：不传 catRuleIds 的默认查询会漏商品（2026-10-12 实测默认 50 件，
      逐类目枚举 53 件，漏掉的 3 件中有 2 件是真能兑的）。
      因此必须按 catRuleIds 逐类目查询后合并，不能只依赖默认查询。

      --detail: mall-product-detail 的返回（可重复传）。列表接口**不含** extTradePrice，
      只有详情能拿到「券核销额外支付金额」。
      ⚠️ 实测：2026-10-12 真可兑 9 件**全部** extTradePrice > 0，
      即积分商城里没有任何一件是纯积分白拿的。不传 --detail 就等于默认"免费"，会误导用户。

输出: JSON 到 stdout（含 coverage 段报告合并增益、hidden_cost 段报告隐藏现金成本）
"""

import argparse
import json
import re
import sys
from datetime import datetime

TIME_FMT = "%Y-%m-%d %H:%M:%S"
# 积分商品的 price 字段恒为 "0"，真实市价藏在商品名里："6.9元可乐麦炫酷"
PRICE_IN_NAME = re.compile(r"(\d+(?:\.\d+)?)\s*元")
# 稀有度阈值（见规划 11.1）
RARITY_RULES = [
    (5000, "传说", "★★★★★", "🔱"),
    (2000, "史诗", "★★★★☆", "💎"),
    (500, "稀有", "★★★☆☆", "🔷"),
    (1, "普通", "★☆☆☆☆", "⚪"),
]


def to_int(v, default=0):
    try:
        return int(float(str(v).strip()))
    except (TypeError, ValueError):
        return default


def parse_time(s):
    if not s:
        return None
    try:
        return datetime.strptime(str(s).strip(), TIME_FMT)
    except ValueError:
        return None


def extract_market_price(item):
    """从商品名解析券面价（= 到店核销时需另付的现金）。

    注意：这不是商品市价。积分商品的 price 字段恒为 "0"，
    商品名里的数字实测与 extTradePrice 恒等（见 SKILL.md 数据陷阱第 2 条）。
    """
    try:
        p = float(str(item.get("price", "0")).strip())
    except (TypeError, ValueError):
        p = 0.0
    if p > 0:
        return p
    m = PRICE_IN_NAME.search(item.get("spuName", "") or "")
    return float(m.group(1)) if m else None


def rarity_of(point):
    for threshold, label, stars, icon in RARITY_RULES:
        if point >= threshold:
            return {"level": label, "stars": stars, "icon": icon}
    return {"level": "普通", "stars": "★☆☆☆☆", "icon": "⚪"}


def classify(item, now):
    """返回 (bucket, meta)。只依据字段判定，缺字段不臆断。"""
    point_raw = item.get("point")
    point = to_int(point_raw)
    price = to_int(item.get("price"))
    # 缺 status 不默认当作"上架"——未知状态一律不臆断（数据陷阱规则5）
    status_raw = item.get("status")
    status = to_int(status_raw) if status_raw not in (None, "") else None
    down = parse_time(item.get("downTime"))

    meta = {
        "spuId": item.get("spuId"),
        "name": item.get("spuName"),
        "point": point,
        "price": price,
        "catName": item.get("catName"),
        "upTime": item.get("upTime"),
        "downTime": item.get("downTime"),
        "status": status,
    }

    # 现金商品：point=0 且 price>0（派对/品鉴会/体验营）
    if point == 0 and price > 0:
        meta["reason"] = "现金商品，非积分兑换"
        return "cash_only", meta

    # 缺积分字段：既非现金商品也无积分信息，无法判断，不臆断
    if (point_raw is None or str(point_raw).strip() == "") and price <= 0:
        meta["reason"] = "缺少 point 字段，无法判断"
        return "unknown_expiry", meta

    # 缺下架时间：无法判时效，不臆断
    if down is None:
        meta["reason"] = "缺少 downTime，时效未知"
        return "unknown_expiry", meta

    meta["days_left"] = (down - now).days
    market = extract_market_price(item)
    # 语义澄清：从 spuName 解析出的数字**不是商品市价**，
    # 而是「券面价」= 到店核销时需另付的现金（实测与 extTradePrice 恒等）。
    meta["coupon_price"] = market
    meta["market_price"] = market      # 旧字段名，保留兼容；语义同 coupon_price
    meta["unit_price"] = round(point / market, 2) if market else None
    # 隐藏现金成本：只有 --detail 能补出，列表接口拿不到
    meta["cash_on_top"] = None
    meta["pure_points"] = None         # True = 纯积分白拿（实测 9 件中 0 件）
    meta["sku_id"] = None
    rarity = rarity_of(point)
    meta["rarity"] = rarity["level"]
    meta["stars"] = rarity["stars"]
    meta["icon"] = rarity["icon"]
    # 限时掉落：≤7 天 ⚠️，≤3 天 🔴
    meta["is_limited_drop"] = 0 < meta["days_left"] <= 7
    meta["drop_flag"] = (
        "🔴" if 0 < meta["days_left"] <= 3
        else "⚠️" if 0 < meta["days_left"] <= 7
        else ""
    )

    if down <= now:
        meta["reason"] = "已过下架时间（名存实亡）"
        return "extinct", meta
    if status == 3:
        meta["reason"] = "售罄"
        return "extinct", meta

    # status 白名单：只有确认"上架"(2)才判可兑。
    # 官方未定义的状态码（0/6/99…）与缺字段一律不臆断——
    # 否则官方新增一个状态就会被静默当成"真可兑"，这是最危险的一类错。
    if status != 2:
        if status is None:
            meta["reason"] = "缺少 status 字段，不臆断"
        elif status in (1, 4, 5):
            meta["reason"] = f"未上架(status={status})"
        else:
            meta["reason"] = f"状态未知(status={status})，不臆断"
        return "unknown_expiry", meta

    return "redeemable", meta


def load_items(path):
    """读一个输入文件，返回商品数组。"""
    with open(path, "r", encoding="utf-8") as f:
        raw = json.load(f)
    items = raw.get("data", raw) if isinstance(raw, dict) else raw
    if not isinstance(items, list):
        raise ValueError(f"{path} 中未找到商品数组")
    return items


def merge_items(paths):
    """按 spuId 去重合并多份返回，并记录每份的增量贡献。"""
    merged = {}
    coverage = []
    for p in paths:
        items = load_items(p)
        added = 0
        for it in items:
            sid = it.get("spuId")
            if sid is None:
                continue
            if sid not in merged:
                merged[sid] = it
                added += 1
        coverage.append({
            "input": p,
            "returned": len(items),
            "new_after_dedup": added,
            "cumulative": len(merged),
        })
    return list(merged.values()), coverage


def load_details(paths):
    """读若干份 mall-product-detail 返回，返回 {spuId: detail}。"""
    out = {}
    for p in paths:
        with open(p, "r", encoding="utf-8") as f:
            raw = json.load(f)
        # 支持三种形态：{details:[...]} / {data:{...}}（单次调用） / [ {...}, {...} ]
        if isinstance(raw, dict):
            if isinstance(raw.get("details"), list):
                items = raw["details"]
            elif isinstance(raw.get("data"), dict):
                items = [raw["data"]]
            elif isinstance(raw.get("data"), list):
                items = raw["data"]
            else:
                raise ValueError(f"{p} 中未找到详情对象")
        else:
            items = raw
        for d in items:
            sid = d.get("spuId")
            if sid is not None:
                out[sid] = d
    return out


def apply_detail(meta, detail):
    """把详情里的 skuList 关键信息并入 meta。不做任何主观判断。"""
    skus = detail.get("skuList") or []
    metas = []
    for s in skus:
        try:
            metas.append({
                "skuId": s.get("skuId"),
                "points": to_int(s.get("points")),
                "extTradePrice": float(str(s.get("extTradePrice", "0")).strip() or 0),
            })
        except (TypeError, ValueError):
            continue
    if not metas:
        return
    # 单 SKU 直接取；多 SKU 取最低现金附加，并保留全部取值供展示
    cheapest = min(metas, key=lambda x: (x["extTradePrice"], x["points"]))
    meta["sku_id"] = cheapest["skuId"]
    meta["cash_on_top"] = cheapest["extTradePrice"]
    meta["pure_points"] = cheapest["extTradePrice"] == 0
    if len({m["extTradePrice"] for m in metas}) > 1:
        meta["cash_on_top_variants"] = [m["extTradePrice"] for m in metas]
    meta["spu_category"] = detail.get("spuCategory")
    meta["shop_id"] = detail.get("shopId")
    # 详情的时间字段叫 upDate/downDate，与列表的 upTime/downTime 不同名（官方不一致）
    if detail.get("downDate"):
        meta["detail_down_time"] = detail.get("downDate")


def points_value(redeemable, point):
    """把积分按「最优兑换出口」折算成人民币现值。

    口径说明（全部由本仓库实测数据算出）：
        best_rate     = min(unit_price)   # 分/元，每花 1 元需付多少积分，越小越划算
        每100积分现值  = 100 / best_rate   # 元
        积分现值       = point / best_rate # 元

    为什么需要它：
        用户对「7.25 分/元」没有感知，对「100 分现值 ¥13.79」有感知。
        积分是资产，资产就该有账面价值。

    参数:
        redeemable: classify + apply_detail 后的真可兑 meta 列表
        point:      可用积分（None / 缺失 → 总现值返回 None，不臆断）

    返回 dict；无任何带价出口时返回 None（不臆断）。
    """
    priced = [m for m in redeemable if m.get("unit_price")]
    if not priced:
        return None
    best = min(priced, key=lambda m: m["unit_price"])
    rate = best["unit_price"]          # 分/元
    value_per_100 = round(100.0 / rate, 2)
    total = None if point is None else round(float(point) / rate, 2)
    return {
        "point": point,
        "best_rate_per_yuan": rate,          # 分/元（最优出口汇率）
        "value_per_100": value_per_100,      # 每 100 积分现值（元）
        "total_value": total,                # 该笔积分的账面现值（元）
        "best_exit": best["name"],           # 最优出口商品名
        "best_exit_point": best["point"],
        "best_exit_cash": best.get("cash_on_top"),
        "exit_count": len(priced),           # 参与折算的出口数
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--input", action="append", required=True,
                    help="mall-points-products 原始 JSON 路径，可重复传入以合并多个类目查询")
    ap.add_argument("--detail", action="append", default=[],
                    help="mall-product-detail 返回路径，可重复传入；用于补出隐藏现金成本 extTradePrice")
    ap.add_argument("--available-point", type=int, default=None,
                    help="可用积分（query-my-account 的 availablePoint）；传入则额外输出积分现值折算")
    ap.add_argument("--now", default=None, help=f'基准时间 "{TIME_FMT}"，默认取当前时间')
    args = ap.parse_args()

    try:
        items, coverage = merge_items(args.input)
    except Exception as e:
        print(json.dumps({"error": f"无法解析输入: {e}"}, ensure_ascii=False))
        return 2

    try:
        details = load_details(args.detail) if args.detail else {}
    except Exception as e:
        print(json.dumps({"error": f"无法解析 --detail: {e}"}, ensure_ascii=False))
        return 2

    now = parse_time(args.now) or datetime.now()

    buckets = {"redeemable": [], "extinct": [], "cash_only": [], "unknown_expiry": []}
    for it in items:
        bucket, meta = classify(it, now)
        d = details.get(it.get("spuId"))
        if d:
            apply_detail(meta, d)
        buckets[bucket].append(meta)

    # 性价比升序：unit_price 越小越划算；无市价者排末尾
    buckets["redeemable"].sort(
        key=lambda x: (x["unit_price"] is None, x["unit_price"] or 0, x["point"])
    )
    buckets["extinct"].sort(key=lambda x: -x["point"])

    # 同名陷阱检测：名字相同但积分不同的商品（实测「10.9元指定小食任选」100分 vs 200分）
    by_name = {}
    for m in buckets["redeemable"] + buckets["extinct"]:
        by_name.setdefault(m["name"], []).append(m)
    name_traps = [
        {"name": n, "variants": [
            {"spuId": v["spuId"], "point": v["point"], "downTime": v["downTime"]}
            for v in sorted(vs, key=lambda x: x["point"])
        ]}
        for n, vs in by_name.items()
        if len(vs) > 1 and len({v["point"] for v in vs}) > 1
    ]

    # 隐藏现金成本汇总：只统计「真可兑」且已补出 extTradePrice 的项
    priced = [m for m in buckets["redeemable"] if m.get("cash_on_top") is not None]
    with_cash = [m for m in priced if m["cash_on_top"] > 0]
    hidden_cost = {
        "redeemable_total": len(buckets["redeemable"]),
        "detail_matched": len(priced),
        "with_cash_on_top": len(with_cash),
        "pure_points": len(priced) - len(with_cash),
        "cash_min": min((m["cash_on_top"] for m in priced), default=None),
        "cash_max": max((m["cash_on_top"] for m in priced), default=None),
        "warning": (
            None if not priced else
            ("全部需到店另付现金，无一件是纯积分白拿" if not (len(priced) - len(with_cash))
             else f"{len(with_cash)}/{len(priced)} 件需到店另付现金")
        ),
    }

    out = {
        "now": now.strftime(TIME_FMT),
        "total_raw": len(items),
        "coverage": coverage,
        "hidden_cost": hidden_cost,
        "points_value": points_value(buckets["redeemable"], args.available_point),
        "redeemable": buckets["redeemable"],
        "extinct": buckets["extinct"],
        "cash_only": buckets["cash_only"],
        "unknown_expiry": buckets["unknown_expiry"],
        "name_traps": name_traps,
    }
    print(json.dumps(out, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
