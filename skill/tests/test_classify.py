#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
classify() 边界与白名单测试。

这些用例覆盖的"非常规状态"在真实 fixture 的 77 件商品里从未出现
（实测 status 全部为 2、point/downTime 无一缺失）——正因为实测数据干净，
才必须用断言把它们钉死：官方接口一旦新增状态码或返回缺字段的商品，
脚本应当"不臆断"而不是静默给出错误答案。

运行:
    python tests/test_classify.py
"""

import json
import os
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.join(HERE, "..")
SCRIPT = os.path.join(ROOT, "scripts", "rank_products.py")
NOW = "2026-10-12 20:00:00"
BUCKETS = ("redeemable", "extinct", "cash_only", "unknown_expiry")
PASS, FAIL = 0, 0

BASE = {
    "spuName": "6.9元可乐麦炫酷",
    "spuId": 100,
    "point": "50",
    "price": "0",
    "upTime": "2026-10-01 00:00:00",
    "downTime": "2026-12-30 23:59:59",
    "catName": "商品券",
    "status": 2,
}


def check(name, got, want):
    global PASS, FAIL
    if got == want:
        PASS += 1
        print("  ✓ " + name)
    else:
        FAIL += 1
        print("  ✗ " + name + "\n      got=%r want=%r" % (got, want))


def variant(spu_id, drop=(), **kw):
    item = dict(BASE)
    for k in drop:
        item.pop(k, None)
    item["spuId"] = spu_id
    item.update(kw)
    return item


BUCKET_CASES = [
    (101, "redeemable",     {}),
    (102, "extinct",        {"downTime": "2026-10-01 00:00:00"}),
    (103, "extinct",        {"status": 3}),
    (104, "unknown_expiry", {"status": 1}),
    (105, "unknown_expiry", {"status": 5}),
    (106, "unknown_expiry", {"status": 0}),
    (107, "unknown_expiry", {"status": 99}),
    (108, "unknown_expiry", {"drop": ("status",)}),
    (109, "unknown_expiry", {"point": ""}),
    (110, "unknown_expiry", {"drop": ("downTime",)}),
    (111, "unknown_expiry", {"downTime": "not-a-time"}),
    (112, "cash_only",      {"point": "0", "price": "199"}),
]

META_CASES = [
    (113, {"downTime": "2026-10-17 20:00:00"}, {"days_left": 5, "is_limited_drop": True, "drop_flag": "⚠️"}),
    (114, {"downTime": "2026-10-14 20:00:00"}, {"days_left": 2, "is_limited_drop": True, "drop_flag": "🔴"}),
    (115, {"downTime": "2026-10-12 20:00:00"}, {"bucket": "extinct"}),
    (116, {"downTime": "2026-10-12 20:30:00"}, {"days_left": 0, "is_limited_drop": False, "drop_flag": ""}),
    (117, {"downTime": "2026-10-20 20:00:00"}, {"days_left": 8, "is_limited_drop": False, "drop_flag": ""}),
]


def run(items):
    fd, path = tempfile.mkstemp(suffix=".json", prefix="classify_")
    os.close(fd)
    with open(path, "w", encoding="utf-8") as f:
        json.dump({"_meta": {"note": "test"}, "data": items}, f, ensure_ascii=False)
    try:
        p = subprocess.run(
            [sys.executable, SCRIPT, "--input", path, "--now", NOW],
            capture_output=True, text=True, encoding="utf-8",
        )
        assert p.returncode == 0, p.stderr
        return json.loads(p.stdout)
    finally:
        os.remove(path)


def locate(out, spu_id):
    for bucket in BUCKETS:
        for item in out.get(bucket, []):
            if item.get("spuId") == spu_id:
                return bucket, item
    return None, None


def main():
    print("=" * 60)
    print("classify · 边界与白名单测试")
    print("=" * 60)

    all_items = [variant(i, **kw) for i, _, kw in BUCKET_CASES]
    all_items += [variant(i, **kw) for i, kw, _ in META_CASES]
    out = run(all_items)

    print("\n[1] bucket 分类（未知 status 不得当可兑）")
    for spu_id, want, _ in BUCKET_CASES:
        got, _item = locate(out, spu_id)
        check("spuId=%d → %s" % (spu_id, want), got, want)

    print("\n[2] 不臆断：归入 unknown_expiry 必须给出原因")
    for spu_id, want, _ in BUCKET_CASES:
        if want != "unknown_expiry":
            continue
        _b, item = locate(out, spu_id)
        reason = (item or {}).get("reason")
        check("spuId=%d 有 reason" % spu_id, bool(reason) and len(str(reason)) > 4, True)

    print("\n[3] 临期分级与 is_limited_drop / drop_flag 一致性")
    for spu_id, _kw, want in META_CASES:
        bucket, item = locate(out, spu_id)
        if "bucket" in want:
            check("spuId=%d → %s" % (spu_id, want["bucket"]), bucket, want["bucket"])
            continue
        for field, expected in want.items():
            check("spuId=%d %s=%r" % (spu_id, field, expected), (item or {}).get(field), expected)

    print("\n[4] 无丢失：所有用例均被分类")
    placed = sum(len(out.get(b, [])) for b in BUCKETS)
    check("分类总数 = 用例总数", placed, len(all_items))

    print("\n[5] 核心保障：未知 status 零流入可兑榜")
    bad = [i.get("spuId") for i in out.get("redeemable", []) if i.get("status") != 2]
    check("redeemable 中无非 status=2 商品", bad, [])

    print("\n" + "=" * 60)
    print("总计 %d 项，通过 %d，失败 %d" % (PASS + FAIL, PASS, FAIL))
    print("=" * 60)
    return 1 if FAIL else 0


if __name__ == "__main__":
    sys.exit(main())
