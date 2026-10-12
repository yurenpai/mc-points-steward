#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
积分现值折算测试（points_value）。

为什么单独立一个文件：
    竞品 mcd-points-vault 用「每 100 积分兑 X 元」表达积分价值，比「分/元」直观。
    我们把同一口径做实，全部数字由 fixtures 真实数据算出，不手抄。
    这个指标是新增门面，必须钉死，防止以后改排序逻辑时把它带坏。

运行:
    python tests/test_points_value.py
"""

import json
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.join(HERE, "..")
SCRIPT = os.path.join(ROOT, "scripts", "rank_products.py")
FIX = os.path.join(HERE, "fixtures")
CAT14 = os.path.join(FIX, "mall_products_cat_1_4_20261012.json")
CAT28 = os.path.join(FIX, "mall_products_cat_2_8_20261012.json")
DETAIL = os.path.join(FIX, "mall_details_20261012.json")
NOW = "2026-10-12 20:00:00"
PASS, FAIL = 0, 0


def check(name, got, want):
    global PASS, FAIL
    if got == want:
        PASS += 1
        print(f"  ✓ {name}")
    else:
        FAIL += 1
        print(f"  ✗ {name}\n      got={got!r} want={want!r}")


def run(point=None):
    cmd = [sys.executable, SCRIPT,
           "--input", CAT14, "--input", CAT28,
           "--detail", DETAIL, "--now", NOW]
    if point is not None:
        cmd += ["--available-point", str(point)]
    p = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8")
    assert p.returncode == 0, p.stderr
    return json.loads(p.stdout)


def main():
    out = run(3260)
    pv = out["points_value"]

    print("== 1. 现值口径：每 100 积分值多少钱 ==")
    check("最优出口汇率 7.25 分/元", pv["best_rate_per_yuan"], 7.25)
    check("每 100 积分现值 = 100/7.25", pv["value_per_100"], 13.79)
    check("最优出口商品", pv["best_exit"], "6.9元可乐麦炫酷")
    check("最优出口积分", pv["best_exit_point"], 50)
    check("参与折算的出口数 = 真可兑件数", pv["exit_count"], len(out["redeemable"]))

    print("== 2. 总现值：积分 / 汇率 ==")
    check("3260 分现值 = 3260/7.25", pv["total_value"], 449.66)
    check("传入的积分原样带回", pv["point"], 3260)

    print("== 3. 与 unit_price 最小值自洽（防止两处逻辑漂移） ==")
    ups = [r["unit_price"] for r in out["redeemable"] if r["unit_price"] is not None]
    check("最优汇率即 unit_price 最小值", pv["best_rate_per_yuan"], min(ups))
    check("每100积分现值 = 100/min(unit_price)", pv["value_per_100"], round(100.0 / min(ups), 2))

    print("== 4. 边界：0 分不是 None ==")
    zero = run(0)["points_value"]
    check("0 分现值 0.0（真实结果，不是缺数据）", zero["total_value"], 0.0)
    check("0 分仍给出汇率（攒分前也有参考）", zero["value_per_100"], 13.79)

    print("== 5. 边界：不传积分则总现值为 None（不臆断） ==")
    none = run()["points_value"]
    check("未传 availablePoint → total_value=None", none["total_value"], None)
    check("未传时汇率依然可用", none["value_per_100"], 13.79)

    print("== 6. 边界：没有任何带价出口 → None ==")
    empty = os.path.join(HERE, "_tmp_no_price.json")
    with open(empty, "w", encoding="utf-8") as f:
        json.dump({"data": [{"spuId": 999, "spuName": "无价商品", "point": 100,
                             "status": 2, "downTime": "2027-01-01 00:00:00"}]}, f)
    p = subprocess.run([sys.executable, SCRIPT, "--input", empty,
                        "--available-point", "500", "--now", NOW],
                       capture_output=True, text=True, encoding="utf-8")
    os.remove(empty)
    check("无带价商品时 points_value=None", json.loads(p.stdout)["points_value"], None)

    print("== 7. demo 账本段带出现值（门面不能只有 JSON 有） ==")
    demo = subprocess.run([sys.executable, os.path.join(ROOT, "scripts", "demo.py"),
                           "--section", "1"],
                          capture_output=True, text=True, encoding="utf-8")
    check("demo 退出码 0", demo.returncode, 0)
    check("账本段含「资产现值」小节", "资产现值" in demo.stdout, True)
    check("账本段含「每 100 积分现值 ¥13.79」", "每 100 积分现值 ¥13.79" in demo.stdout, True)

    print(f"\n{'ALL PASS' if FAIL == 0 else 'HAS FAILURE'}  通过 {PASS} / 失败 {FAIL}")
    return 1 if FAIL else 0


if __name__ == "__main__":
    sys.exit(main())
