#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
test_cat_merge.py —— 类目合并与「默认查询漏报」回归测试

锁死 2026-10-12 实测结论（见 SKILL.md 数据陷阱第 8 条）：
  默认查询（不传 catRuleIds）返回不完整，漏掉的恰好是真能兑的商品。
  因此必须逐类目查询后按 spuId 合并。

运行：python tests/test_cat_merge.py
"""

import json
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
SKILL = os.path.dirname(HERE)
FIX = os.path.join(SKILL, "tests", "fixtures")
PY = sys.executable

NOW = "2026-10-12 16:07:00"

passed, failed = 0, 0


def check(label, ok, detail=""):
    global passed, failed
    if ok:
        passed += 1
        print(f"  ✓ {label}")
    else:
        failed += 1
        print(f"  ✗ {label}  {detail}")


def load(name):
    with open(os.path.join(FIX, name), "r", encoding="utf-8") as f:
        raw = json.load(f)
    d = raw.get("data", raw)
    return d if isinstance(d, list) else []


def run_rank(inputs, now=NOW):
    cmd = [PY, os.path.join(SKILL, "scripts", "rank_products.py")]
    for i in inputs:
        cmd += ["--input", os.path.join(FIX, i)]
    cmd += ["--now", now]
    r = subprocess.run(cmd, capture_output=True, text=True,
                       encoding="utf-8", errors="replace")
    assert r.returncode == 0, r.stdout + r.stderr
    return json.loads(r.stdout)


print("=" * 58)
print("类目合并与默认查询漏报 · 回归测试")
print("=" * 58)

# ---------------------------------------------------------------- 1
print("\n== 1. 各类目快照本身 ==")
c14 = load("mall_products_cat_1_4_20261012.json")
c28 = load("mall_products_cat_2_8_20261012.json")
dflt = load("mall_products_20261012.json")

check("1>4 商品券 24 件", len(c14) == 24, f"实际 {len(c14)}")
check("2>8 周边 3 件", len(c28) == 3, f"实际 {len(c28)}")
check("默认查询 50 件", len(dflt) == 50, f"实际 {len(dflt)}")

# 周边三件全部过期
check("周边三件 downTime 均已过期",
      all(i["downTime"] < NOW for i in c28),
      str([i["downTime"] for i in c28]))

# ---------------------------------------------------------------- 2
print("\n== 2. 合并结果 ==")
out = run_rank(["mall_products_cat_1_4_20261012.json",
                "mall_products_cat_2_8_20261012.json"])

check("合并后 27 件（去重）", out["total_raw"] == 27, f"实际 {out['total_raw']}")
check("真可兑 9 件", len(out["redeemable"]) == 9, f"实际 {len(out['redeemable'])}")
check("绝版 18 件", len(out["extinct"]) == 18, f"实际 {len(out['extinct'])}")
check("现金类 0 件（本快照只查积分类目）",
      len(out["cash_only"]) == 0, f"实际 {len(out['cash_only'])}")

# ---------------------------------------------------------------- 3
print("\n== 3. 默认查询漏报（核心） ==")
dflt_ids = set(i["spuId"] for i in dflt)
missed = [r for r in out["redeemable"] if r["spuId"] not in dflt_ids]

check("默认查询漏掉的可兑商品为 2 件", len(missed) == 2, f"实际 {len(missed)}")
check("漏掉的两件是 17075 / 17078",
      sorted(r["spuId"] for r in missed) == [17075, 17078],
      str(sorted(r["spuId"] for r in missed)))
names = sorted(r["name"] for r in missed)
check("漏掉的确实是真能兑的（3.9元圆筒冰淇淋 / 16.9元2份麦辣鸡翅）",
      any("圆筒冰淇淋" in n for n in names) and any("麦辣鸡翅" in n for n in names),
      str(names))

# 仅用默认查询跑一次，验证它会少报
out_default = run_rank(["mall_products_20261012.json"])
check("只查默认 → 真可兑仅 7 件（错误答案）",
      len(out_default["redeemable"]) == 7, f"实际 {len(out_default['redeemable'])}")
check("逐类目补全 → 多出 2 件（正确答案 9）",
      len(out["redeemable"]) - len(out_default["redeemable"]) == 2,
      f"实际 {len(out['redeemable']) - len(out_default['redeemable'])}")

# ---------------------------------------------------------------- 4
print("\n== 4. 同名陷阱 ==")
traps = out["name_traps"]
check("检出 1 组同名陷阱", len(traps) == 1, f"实际 {len(traps)}")
if traps:
    t = traps[0]
    pts = sorted(v["point"] for v in t["variants"])
    check("同名两件的积分为 100 / 200（差一倍）", pts == [100, 200], str(pts))
    check("陷阱商品名为「10.9元指定小食任选」",
          "10.9元指定小食任选" in t["name"], t["name"])

# ---------------------------------------------------------------- 5
print("\n== 5. 性价比排序（脚本输出的确定性） ==")
red = out["redeemable"]
vals = [r["unit_price"] for r in red if r["unit_price"] is not None]
check("全部可兑商品都解析出市价", len(vals) == len(red), f"{len(vals)}/{len(red)}")
check("按 分/元 升序排列", vals == sorted(vals), str(vals))
check("最优 7.25 分/元", abs(vals[0] - 7.25) < 1e-6, str(vals[0]))
check("最差 36.53 分/元", abs(vals[-1] - 36.53) < 1e-6, str(vals[-1]))
check("最优与最差相差 5 倍以上", vals[-1] / vals[0] > 5.0,
      f"{vals[-1] / vals[0]:.2f} 倍")

# ---------------------------------------------------------------- 6
print("\n== 6. coverage 段（合并增益可追溯） ==")
cov = out["coverage"]
check("coverage 记录 2 份输入", len(cov) == 2, f"实际 {len(cov)}")
check("累计件数递增到 27", cov[-1]["cumulative"] == 27, str(cov[-1]))

# ---------------------------------------------------------------- 7
print("\n== 7. 时间旅行：到期前会亮限时掉落 ==")
out_late = run_rank(["mall_products_cat_1_4_20261012.json",
                     "mall_products_cat_2_8_20261012.json"],
                    now="2026-12-28 12:00:00")
drops = [r for r in out_late["redeemable"] if r.get("is_limited_drop")]
check("2026-12-28 视角下 9 件均为限时掉落", len(drops) == 9, f"实际 {len(drops)}")
check("且全部标 🔴（≤3 天）", all(r["drop_flag"] == "🔴" for r in drops),
      str([r["drop_flag"] for r in drops]))

# ---------------------------------------------------------------- 汇总
print("\n" + "=" * 58)
print(f"{'ALL PASS' if failed == 0 else 'HAS FAILURE'}  通过 {passed} / 失败 {failed}")
print("=" * 58)
sys.exit(1 if failed else 0)
