#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
性价比排序测试。

运行:
    python tests/test_rank.py
"""

import json
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.join(HERE, "..")
SCRIPT = os.path.join(ROOT, "scripts", "rank_products.py")
FIXTURE = os.path.join(HERE, "fixtures", "mall_products_20261012.json")
PASS, FAIL = 0, 0


def check(name, got, want):
    global PASS, FAIL
    if got == want:
        PASS += 1
        print(f"  ✓ {name}")
    else:
        FAIL += 1
        print(f"  ✗ {name}\n      got={got!r} want={want!r}")


def run_script(now):
    p = subprocess.run(
        [sys.executable, SCRIPT, "--input", FIXTURE, "--now", now],
        capture_output=True, text=True, encoding="utf-8",
    )
    assert p.returncode == 0, p.stderr
    return json.loads(p.stdout)


def main():
    out = run_script("2026-10-12 14:55:00")

    print("== 1. 排序：按 unit_price 升序（越前越划算） ==")
    ups = [r["unit_price"] for r in out["redeemable"] if r["unit_price"] is not None]
    check("单价序列单调不减", ups == sorted(ups), True)
    check("榜首单价最低", ups[0], 7.25)
    check("榜首商品", out["redeemable"][0]["name"], "6.9元可乐麦炫酷")

    print("== 2. 无市价者排末尾且不参与单价 ==")
    no_price = [r for r in out["redeemable"] if r["unit_price"] is None]
    check("当前真可兑商品均有市价可解析", len(no_price), 0)

    print("== 3. 性价比计算正确性 ==")
    target = next(r for r in out["redeemable"] if r["name"] == "21.9元巨无霸可乐组合")
    check("21.9元巨无霸可乐组合 = 800/21.9", target["unit_price"], 36.53)

    print("== 4. 稀有度分级 ==")
    rarity = {r["name"]: r["rarity"] for r in out["redeemable"]}
    check("50 分为普通", rarity["6.9元可乐麦炫酷"], "普通")
    check("500 分为稀有", rarity["16.9元麦辣可乐组合"], "稀有")

    print("== 5. 临期标记：当前无 ≤7 天商品 ==")
    check("限时掉落数量为 0（最近一批 12-30 到期）",
          sum(1 for r in out["redeemable"] if r["is_limited_drop"]), 0)

    print("== 6. 时间旅行：切到 2026-12-28 应出现限时掉落 ==")
    later = run_script("2026-12-28 10:00:00")
    drops = [r for r in later["redeemable"] if r["is_limited_drop"]]
    check("12-28 视角下 7 件均为限时掉落", len(drops), len(later["redeemable"]))

    print("== 7. 空输入不崩 ==")
    empty = os.path.join(HERE, "_tmp_empty.json")
    with open(empty, "w", encoding="utf-8") as f:
        json.dump({"data": []}, f)
    p = subprocess.run([sys.executable, SCRIPT, "--input", empty],
                       capture_output=True, text=True, encoding="utf-8")
    os.remove(empty)
    check("空数组返回码 0", p.returncode, 0)
    check("空数组结果为空榜", json.loads(p.stdout)["redeemable"], [])

    print(f"\n{'ALL PASS' if FAIL == 0 else 'HAS FAILURE'}  通过 {PASS} / 失败 {FAIL}")
    return 1 if FAIL else 0


if __name__ == "__main__":
    sys.exit(main())
