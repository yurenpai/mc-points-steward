#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
去伪规则测试 —— 本 Skill 的核心卖点，必须钉死。

运行:
    python tests/test_filter.py
（不依赖 pytest，标准库即可跑，降低评审者运行门槛）
"""

import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "scripts"))
from rank_products import classify, extract_market_price, parse_time  # noqa: E402

FIXTURE = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                       "fixtures", "mall_products_20261012.json")
NOW = parse_time("2026-10-12 14:55:00")
PASS, FAIL = 0, 0


def check(name, got, want):
    global PASS, FAIL
    if got == want:
        PASS += 1
        print(f"  ✓ {name}")
    else:
        FAIL += 1
        print(f"  ✗ {name}\n      got={got!r} want={want!r}")


def bucket_of(item):
    return classify(item, NOW)[0]


def main():
    print("== 1. 假上架：status=2 但 downTime 已过 → extinct ==")
    check("Nike 联名（兑换窗 2026-06-05 两小时）",
          bucket_of({"spuName": "Nike Book 2", "spuId": 16800, "point": "8888",
                     "price": "0", "status": 2, "downTime": "2026-06-05 16:00:00"}),
          "extinct")
    check("罗技键鼠（2026-08-21 已结束）",
          bucket_of({"spuName": "罗技键鼠套装", "spuId": 17694, "point": "6666",
                     "price": "0", "status": 2, "downTime": "2026-08-21 23:59:59"}),
          "extinct")

    print("== 2. 边界：downTime == now → 视为已过期（ extinct ） ==")
    check("恰好等于当前时刻",
          bucket_of({"spuName": "边界商品", "spuId": 1, "point": "100",
                     "price": "0", "status": 2, "downTime": "2026-10-12 14:55:00"}),
          "extinct")

    print("== 3. 现金商品：point=0 且 price>0 → cash_only ==")
    check("生日派对 50 元",
          bucket_of({"spuName": "麦当劳奇妙生日派对", "spuId": 1779, "point": "0",
                     "price": "50", "status": 2, "downTime": "2027-12-31 23:59:59"}),
          "cash_only")

    print("== 4. 售罄：status=3 → extinct ==")
    check("售罄商品不进可兑榜",
          bucket_of({"spuName": "已售罄", "spuId": 2, "point": "100",
                     "price": "0", "status": 3, "downTime": "2027-01-01 00:00:00"}),
          "extinct")

    print("== 5. 缺 downTime → unknown_expiry（不臆断时效） ==")
    check("缺字段不标临期",
          bucket_of({"spuName": "无时效商品", "spuId": 3, "point": "100",
                     "price": "0", "status": 2}),
          "unknown_expiry")

    print("== 6. 市价解析：积分商品 price 恒为 0，须从商品名取 ==")
    check("'6.9元可乐麦炫酷' → 6.9",
          extract_market_price({"spuName": "6.9元可乐麦炫酷", "price": "0"}), 6.9)
    check("'17.9元板烧可乐组合' → 17.9",
          extract_market_price({"spuName": "17.9元板烧可乐组合", "price": "0"}), 17.9)
    check("无金额可解析 → None（不填 0）",
          extract_market_price({"spuName": "罗技键鼠套装", "price": "0"}), None)

    print("== 7. 全量 fixture 统计（真实数据回归） ==")
    with open(FIXTURE, "r", encoding="utf-8") as f:
        items = json.load(f)["data"]
    counts = {"redeemable": 0, "extinct": 0, "cash_only": 0, "unknown_expiry": 0}
    for it in items:
        counts[bucket_of(it)] += 1
    check("原始件数", len(items), 50)
    check("真可兑", counts["redeemable"], 7)
    check("已绝版", counts["extinct"], 17)
    check("现金类", counts["cash_only"], 26)
    check("时效未知", counts["unknown_expiry"], 0)

    print(f"\n{'ALL PASS' if FAIL == 0 else 'HAS FAILURE'}  通过 {PASS} / 失败 {FAIL}")
    return 1 if FAIL else 0


if __name__ == "__main__":
    sys.exit(main())
