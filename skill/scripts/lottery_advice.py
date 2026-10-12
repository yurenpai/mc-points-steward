#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
lottery_advice.py —— 积分抽奖奖池结构解析

设计原则同 rank_products.py：
  本脚本只做确定性解析与分组，输出事实。
  "值不值得抽"的判断一律由 Agent 生成，脚本绝不输出主观建议。

用法:
    python lottery_advice.py --input lottery_raw.json

输出: JSON 到 stdout
"""

import argparse
import json
import re
import sys
from collections import OrderedDict

# 从奖品名解析面额：立减3元 / 5折 / 5.5折 / 30积分
AMOUNT_RE = re.compile(r"(\d+(?:\.\d+)?)")
CASHBACK_RE = re.compile(r"^(\d+(?:\.\d+)?)\s*积分$")


def parse_prize(p):
    name = (p.get("name") or "").strip()
    ptype = p.get("typeText") or "其他"
    m = CASHBACK_RE.match(name)
    if m:
        return {"name": name, "type": ptype, "kind": "cashback",
                "value": float(m.group(1)), "unit": "积分"}
    if "立减" in name:
        am = AMOUNT_RE.search(name)
        return {"name": name, "type": ptype, "kind": "cash_coupon",
                "value": float(am.group(1)) if am else None, "unit": "元"}
    if "折" in name:
        am = AMOUNT_RE.search(name)
        return {"name": name, "type": ptype, "kind": "discount_coupon",
                "value": float(am.group(1)) if am else None, "unit": "折"}
    return {"name": name, "type": ptype, "kind": "other",
            "value": None, "unit": None}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--input", required=True, help="query-lottery-info 原始 JSON 路径")
    args = ap.parse_args()

    try:
        with open(args.input, "r", encoding="utf-8") as f:
            raw = json.load(f)
    except Exception as e:
        print(json.dumps({"error": f"无法解析输入: {e}"}, ensure_ascii=False))
        return 2

    d = raw.get("data", raw) if isinstance(raw, dict) else {}
    if not d:
        print(json.dumps({"error": "输入中未找到 data"}, ensure_ascii=False))
        return 2

    prizes = d.get("prizes") or []
    parsed = [parse_prize(p) for p in prizes]

    groups = OrderedDict()
    for p in parsed:
        groups.setdefault(p["kind"], []).append(p)

    cashbacks = groups.get("cashback", [])
    decision = d.get("drawDecision") or {}

    out = {
        "activity_name": d.get("activityName"),
        "activity_status": d.get("activityStatusText"),
        "end_time": d.get("endTime"),
        "cost_per_draw": d.get("drawPoint"),
        "draw_type": d.get("drawTypeText"),
        "prize_count": len(parsed),
        "groups": {k: len(v) for k, v in groups.items()},
        "prizes": parsed,
        "has_cashback": bool(cashbacks),
        "cashback_value": cashbacks[0]["value"] if cashbacks else None,
        # 资格只取服务端判定，脚本不做任何推断
        "eligible": decision.get("resourceEligible"),
        "ineligible_reason": decision.get("reason"),
        "next_consumption": decision.get("nextConsumption"),
    }
    print(json.dumps(out, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
