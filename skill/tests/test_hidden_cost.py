#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
test_hidden_cost.py —— 「隐藏现金成本」回归测试

锁死 2026-10-12 实测结论（见 SKILL.md 数据陷阱第 9 条）：
  积分商城**真可兑 9 件全部**需要到店另付现金（skuList[].extTradePrice > 0）。
  该字段**只存在于 mall-product-detail**，列表接口 mall-points-products 完全没有。
  → 不看详情就推荐，等于告诉用户"100 积分白拿一个冰淇淋"，实际还要再付 3.9 元。

运行：python tests/test_hidden_cost.py
"""

import json
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
SKILL = os.path.dirname(HERE)
FIX = os.path.join(SKILL, "tests", "fixtures")
SCRIPTS = os.path.join(SKILL, "scripts")
PY = sys.executable

sys.path.insert(0, SCRIPTS)
import rank_products as rp  # noqa: E402

NOW = "2026-10-12 18:34:00"

passed, failed = 0, 0


def check(label, ok, detail=""):
    global passed, failed
    if ok:
        passed += 1
        print(f"  ✓ {label}")
    else:
        failed += 1
        print(f"  ✗ {label}  {detail}")


def run(*args):
    p = subprocess.run(
        [PY, os.path.join(SCRIPTS, "rank_products.py"), *args],
        capture_output=True, text=True, encoding="utf-8",
    )
    return json.loads(p.stdout)


def main():
    with open(os.path.join(FIX, "mall_details_20261012.json"), "r", encoding="utf-8") as f:
        fx = json.load(f)
    details = fx["details"]

    print("\n[1] fixture 完整性")
    check("详情共 9 件（真可兑全量，无抽样）", len(details) == 9, f"实际 {len(details)}")
    check("每件都有 spuId", all(d.get("spuId") for d in details))
    check("每件都有非空 skuList",
          all(d.get("skuList") for d in details),
          str([d.get("spuId") for d in details if not d.get("skuList")]))

    print("\n[2] 核心结论：0 件是纯积分白拿")
    cashy = [d for d in details if float(d["skuList"][0]["extTradePrice"]) > 0]
    check("9 件全部 extTradePrice > 0", len(cashy) == 9, f"仅 {len(cashy)} 件")
    check("不存在 extTradePrice == 0 的商品（纯积分白拿）",
          not any(float(d["skuList"][0]["extTradePrice"]) == 0 for d in details))
    check("列表接口字段里确实没有 extTradePrice（所以必须查详情）",
          "extTradePrice" not in json.dumps(
              json.load(open(os.path.join(FIX, "mall_products_cat_1_4_20261012.json"),
                             encoding="utf-8"))))

    print("\n[3] extTradePrice 与商品名里的数字恒等")
    for d in details:
        m = rp.PRICE_IN_NAME.search(d["spuName"])
        name_yuan = float(m.group(1)) if m else None
        ext = float(d["skuList"][0]["extTradePrice"])
        check(f'  spu{d["spuId"]} 「{d["spuName"]}」名内 {name_yuan} == extTradePrice {ext}',
              name_yuan == ext, f"{name_yuan} != {ext}")

    print("\n[4] 端到端：传入 --detail 后的 hidden_cost 汇总")
    out = run("--input", os.path.join(FIX, "mall_products_cat_1_4_20261012.json"),
              "--input", os.path.join(FIX, "mall_products_cat_2_8_20261012.json"),
              "--detail", os.path.join(FIX, "mall_details_20261012.json"),
              "--now", NOW)
    hc = out.get("hidden_cost", {})
    check("真可兑 9 件", hc.get("redeemable_total") == 9, str(hc.get("redeemable_total")))
    check("详情匹配 9 件", hc.get("detail_matched") == 9, str(hc.get("detail_matched")))
    check("需另付现金 9 件", hc.get("with_cash_on_top") == 9, str(hc.get("with_cash_on_top")))
    check("纯积分白拿 0 件 ← 核心结论", hc.get("pure_points") == 0, str(hc.get("pure_points")))
    check("现金区间 ¥3.9 ~ ¥21.9",
          hc.get("cash_min") == 3.9 and hc.get("cash_max") == 21.9,
          f'{hc.get("cash_min")} ~ {hc.get("cash_max")}')
    check("warning 文案已生成", bool(hc.get("warning")))
    check("redeemable 每项都带 cash_on_top",
          all(r.get("cash_on_top") is not None for r in out["redeemable"]))
    check("redeemable 每项 pure_points 均为 False",
          all(r.get("pure_points") is False for r in out["redeemable"]))
    check("redeemable 每项都带 sku_id（下单要用）",
          all(r.get("sku_id") for r in out["redeemable"]))

    print("\n[5] 不传 --detail 时不臆断（完整性底线）")
    bare = run("--input", os.path.join(FIX, "mall_products_cat_1_4_20261012.json"),
               "--input", os.path.join(FIX, "mall_products_cat_2_8_20261012.json"),
               "--now", NOW)
    check("cash_on_top 全为 None（不猜 0）",
          all(r.get("cash_on_top") is None for r in bare["redeemable"]))
    check("pure_points 全为 None（不猜 True）",
          all(r.get("pure_points") is None for r in bare["redeemable"]))
    check("hidden_cost.pure_points 为 0（未匹配即不计）",
          bare.get("hidden_cost", {}).get("pure_points") == 0)

    print("\n[6] load_details 兼容三种返回形态")
    p = os.path.join(FIX, "mall_details_20261012.json")
    d1 = rp.load_details([p])
    check("{details:[...]} 形态可解析，得 9 件", len(d1) == 9, str(len(d1)))

    tmp_a = os.path.join(HERE, "_tmp_bare_array.json")
    with open(tmp_a, "w", encoding="utf-8") as f:
        json.dump(details, f, ensure_ascii=False)
    check("裸数组形态可解析", len(rp.load_details([tmp_a])) == 9)

    tmp_s = os.path.join(HERE, "_tmp_single.json")
    with open(tmp_s, "w", encoding="utf-8") as f:
        json.dump({"success": True, "data": details[0]}, f, ensure_ascii=False)
    check("{data:{...}} 单次调用形态可解析", len(rp.load_details([tmp_s])) == 1)

    print("\n[7] apply_detail 行为")
    meta = {"spuId": 999, "name": "x", "point": 100}
    rp.apply_detail(meta, {
        "spuId": 999,
        "skuList": [{"skuId": 1, "points": "100", "extTradePrice": "20.0"},
                    {"skuId": 2, "points": "150", "extTradePrice": "9.9"}],
    })
    check("多 SKU 取最低现金附加（9.9 而非 20.0）",
          meta["cash_on_top"] == 9.9, str(meta.get("cash_on_top")))
    check("多 SKU 取对应最低项的 skuId", meta["sku_id"] == 2, str(meta.get("sku_id")))
    check("多 SKU 保留全部取值", meta.get("cash_on_top_variants") == [20.0, 9.9])

    print("\n[8] 绝不解析 note（官方红线：note 须原文展示，不得提取数值）")
    meta2 = {"spuId": 888, "name": "y", "point": 50}
    rp.apply_detail(meta2, {
        "spuId": 888,
        # note 里塞满数字，若脚本误解析就会被污染
        "note": "<p>1.【有效期】本券 3.9 元起，限用 1 张，热线 4009-200-205，10 月 8 日开售</p>",
        "skuList": [{"skuId": 3, "points": "50", "extTradePrice": "6.9"}],
    })
    check("cash_on_top 取自 skuList 而非 note", meta2["cash_on_top"] == 6.9,
          str(meta2.get("cash_on_top")))
    check("未从 note 生成任何字段",
          not any(k.startswith("note") for k in meta2))

    print("\n[9] 修正旧的「同名陷阱」结论：不是同物不同价，而是同名不同物")
    by_name = {}
    for d in details:
        by_name.setdefault(d["spuName"], []).append(d)
    traps = {n: v for n, v in by_name.items() if len(v) > 1}
    check("存在同名商品组", len(traps) == 1, str(list(traps)))
    if traps:
        name, vs = next(iter(traps.items()))
        check(f'  同名组「{name}」积分不同（100 vs 200）',
              len({v["skuList"][0]["points"] for v in vs}) == 2)
        check("  但两者 extTradePrice 相同（都是 10.9）",
              len({v["skuList"][0]["extTradePrice"] for v in vs}) == 1)
        check("  兑换内容不同 → 贵的那个未必是坑，必须展示内容差异",
              len({v.get("_contents") for v in vs}) == 2,
              str([v.get("_contents") for v in vs]))

    print("\n[10] unit_price 语义（已澄清为「每 1 元券面价所需积分」）")
    check("最优 7.25 分/元（50 分 / 6.9 元）",
          out["redeemable"][0]["unit_price"] == 7.25,
          str(out["redeemable"][0]["unit_price"]))
    check("最差 36.53 分/元（800 分 / 21.9 元）",
          out["redeemable"][-1]["unit_price"] == 36.53,
          str(out["redeemable"][-1]["unit_price"]))
    check("coupon_price 与 market_price 同值（兼容别名）",
          all(r["coupon_price"] == r["market_price"] for r in out["redeemable"]))

    for t in (tmp_a, tmp_s):
        if os.path.exists(t):
            os.remove(t)

    print(f"\n{'=' * 46}\n通过 {passed} 项，失败 {failed} 项\n{'=' * 46}")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
