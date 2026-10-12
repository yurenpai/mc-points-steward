#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
麦享掌柜 · 四层项目自检
=======================

把「测试这个项目」压缩成一条命令。四层各司其职：

    L1 断言   保逻辑   —— 跑 tests/ 全部测试文件，汇总断言数
    L2 demo   保形态   —— 跑离线演示，检查三段输出关键锚点仍在
    L3 对账   保链路   —— 快照新鲜度体检（哪些商品可能已变），并给出对话实测四步
    L4 物料   保呈现   —— assets/ 产物在位、XML 合法、GIF 头正确；--rebuild 可重建

用法：
    python verify.py                    # 四层全查（L4 不重建）
    python verify.py --rebuild          # L4 先重建物料再检查
    python verify.py --only L1,L4       # 只查指定层

退出码：0 = 四层全绿；1 = 有失败项；2 = 用法错误。

L3 说明：MCP 是 streamablehttp 长连接，由 WorkBuddy 客户端调度，
本脚本不直连官方接口（也不存 Token）。脚本负责「快照老化体检」，
实时对账请在对话里执行——脚本末尾会打印那四步。
"""

import argparse
import json
import os
import re
import subprocess
import sys
import xml.dom.minidom as minidom
from datetime import datetime

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
SKILL = os.path.join(ROOT, "skill")
ASSETS = os.path.join(ROOT, "assets")
DOCS = os.path.join(ROOT, "docs")

PY = sys.executable
W = 66

L1_TESTS = [
    "test_filter.py", "test_rank.py", "test_cat_merge.py", "test_hidden_cost.py",
    "test_classify.py", "test_points_value.py", "test_report_svg.py",
    "test_demo_gif.py", "test_demo_page.py", "test_banner_svg.py",
    "test_install.py",
]
L2_ANCHORS = [
    "麦享掌柜 · 积分账本",
    "积分商城 · 真实可兑榜单",
    "积分抽奖 · 参谋",
    "资产现值",
]
L4_FILES = [
    (os.path.join("assets", "banner.svg"), "svg"),
    (os.path.join("assets", "report-card.svg"), "svg"),
    (os.path.join("assets", "hidden-cost.svg"), "svg"),
    (os.path.join("assets", "demo.gif"), "gif"),
    (os.path.join("docs", "index.html"), "html"),
]


def line(ch="─"):
    print(ch * W)


def ok(msg):
    print("  [OK]   %s" % msg)


def bad(msg):
    print("  [FAIL] %s" % msg)


def warn(msg):
    print("  [WARN] %s" % msg)


def run_py(args, timeout=120):
    return subprocess.run([PY] + args, capture_output=True, timeout=timeout)


# ---------------------------------------------------------------- L1
def check_l1():
    print("\n■ L1 · 断言回归（保逻辑）")
    line()
    total, failed = 0, []
    for name in L1_TESTS:
        path = os.path.join(SKILL, "tests", name)
        if not os.path.isfile(path):
            bad("%s 不存在" % name)
            failed.append(name)
            continue
        try:
            p = run_py([path])
        except subprocess.TimeoutExpired:
            bad("%s 超时" % name)
            failed.append(name)
            continue
        out = (p.stdout or b"").decode("utf-8", "replace")
        m = re.search(r"总计 (\d+) 项", out) or re.search(r"通过 (\d+)", out)
        n = int(m.group(1)) if m else 0
        has_fail = re.search(r"HAS FAILURE|失败 [1-9]", out) is not None
        total += n
        if p.returncode != 0 or has_fail:
            bad("%s → %d 项，但有失败" % (name, n))
            failed.append(name)
        else:
            ok("%-22s %d 项" % (name, n))
    line()
    if failed:
        bad("L1 不通过：%s" % "、".join(failed))
        return False
    ok("L1 通过：%d 条断言全绿" % total)
    return True


# ---------------------------------------------------------------- L2
def check_l2():
    print("\n■ L2 · 离线演示（保形态）")
    line()
    demo = os.path.join(SKILL, "scripts", "demo.py")
    try:
        p = run_py([demo])
    except subprocess.TimeoutExpired:
        bad("demo.py 超时")
        return False
    out = (p.stdout or b"").decode("utf-8", "replace")
    missing = [a for a in L2_ANCHORS if a not in out]
    if p.returncode != 0:
        bad("demo.py 退出码 %d" % p.returncode)
        return False
    if missing:
        for a in missing:
            bad("输出缺少锚点：%s" % a)
        return False
    ok("三段输出完整（账本 / 榜单 / 抽奖）")
    ok("资产现值小节在位")
    ok("快照声明在位" if "快照" in out else "快照声明缺失")
    if "快照" not in out:
        return False
    line()
    ok("L2 通过")
    return True


# ---------------------------------------------------------------- L3
def check_l3():
    print("\n■ L3 · 快照新鲜度（保链路）")
    line()
    fixture = os.path.join(SKILL, "tests", "fixtures",
                          "mall_products_20261012.json")
    if not os.path.isfile(fixture):
        bad("找不到默认查询 fixture")
        return False
    try:
        items = json.load(open(fixture, encoding="utf-8"))["data"]
    except Exception as e:  # noqa: BLE001
        bad("fixture 解析失败：%s" % e)
        return False

    now = datetime.now()
    still_up, gone, soon = 0, 0, []
    for it in items:
        if int(str(it.get("point", "0") or 0)) <= 0:
            continue  # 现金商品不参与积分时效
        raw = str(it.get("downTime", "") or "").strip()
        try:
            down = datetime.strptime(raw, "%Y-%m-%d %H:%M:%S")
        except ValueError:
            continue
        if down < now:
            gone += 1
        else:
            still_up += 1
            days = (down - now).days
            if days <= 60:
                soon.append((days, it.get("spuName", "?"), raw))
    ok("默认查询快照：积分类 %d 件 = 仍可兑 %d + 已下架 %d（另 2 件真可兑藏在 2>8 类目）"
       % (still_up + gone, still_up, gone))
    if soon:
        soon.sort()
        warn("%d 件可兑商品的下架时间在 60 天内，实时对账时重点核对：" % len(soon))
        for d, name, raw in soon[:5]:
            print("         %-28s %s（剩 %d 天）" % (name[:28], raw[:10], d))
    else:
        ok("60 天内无临近下架的积分类商品")
    line()
    print("  实时对账请在对话里执行（脚本不直连 MCP，也不存 Token）：")
    print("    ① 服务器时间  ② 我的积分  ③ 商城 catRuleIds=1>4")
    print("    ④ 与 fixtures 逐件比对 spuId / point / downTime")
    ok("L3 通过（新鲜度体检完成）")
    return True


# ---------------------------------------------------------------- L4
def check_l4(rebuild=False):
    print("\n■ L4 · 视觉物料（保呈现）%s" % ("[--rebuild]" if rebuild else ""))
    line()
    if rebuild:
        for script in ("make_banner_svg.py", "make_report_svg.py",
                       "make_demo_gif.py", "make_demo_page.py"):
            path = os.path.join(SKILL, "scripts", script)
            print("  重建 %s ..." % script)
            try:
                p = run_py([path], timeout=300)
            except subprocess.TimeoutExpired:
                bad("%s 重建超时" % script)
                return False
            if p.returncode != 0:
                bad("%s 重建失败（退出码 %d）" % (script, p.returncode))
                return False
        line()

    good = True
    for rel, kind in L4_FILES:
        path = os.path.join(ROOT, rel)
        if not os.path.isfile(path):
            bad("%s 缺失" % rel)
            good = False
            continue
        size = os.path.getsize(path)
        try:
            if kind == "svg":
                minidom.parse(path)
            elif kind == "gif":
                with open(path, "rb") as f:
                    head = f.read(6)
                if not head.startswith(b"GIF8"):
                    raise ValueError("GIF 头异常：%r" % head)
            elif kind == "html":
                with open(path, encoding="utf-8") as f:
                    body = f.read()
                if "__SVG__" in body or "__BANNER__" in body:
                    raise ValueError("占位符未替换")
                ext = re.findall(r'(?:src|href)\s*=\s*["\']https?://', body)
                if ext:
                    raise ValueError("含 %d 处外部资源引用（超链接除外）" % len(ext))
        except Exception as e:  # noqa: BLE001
            bad("%s 校验失败：%s" % (rel, e))
            good = False
            continue
        ok("%-26s %6d 字节  校验通过" % (rel, size))
    line()
    if not good:
        bad("L4 不通过")
        return False
    ok("L4 通过")
    return True


LAYERS = {"L1": check_l1, "L2": check_l2, "L3": check_l3, "L4": check_l4}


def main():
    ap = argparse.ArgumentParser(description="麦享掌柜四层项目自检")
    ap.add_argument("--only", default=None,
                    help="只查指定层，逗号分隔，如 L1,L4")
    ap.add_argument("--rebuild", action="store_true",
                    help="L4 先重建物料再检查")
    args = ap.parse_args()

    if args.only:
        picked = [s.strip().upper() for s in args.only.split(",") if s.strip()]
        unknown = [s for s in picked if s not in LAYERS]
        if unknown:
            print("未知层：%s（可用 L1/L2/L3/L4）" % "、".join(unknown))
            return 2
    else:
        picked = ["L1", "L2", "L3", "L4"]

    print("=" * W)
    print("麦享掌柜 · 四层项目自检")
    print("L1 断言保逻辑 · L2 demo 保形态 · L3 对账保链路 · L4 物料保呈现")
    print("=" * W)

    results = {}
    for key in ["L1", "L2", "L3", "L4"]:
        if key not in picked:
            continue
        if key == "L4":
            results[key] = check_l4(rebuild=args.rebuild)
        else:
            results[key] = LAYERS[key]()

    print("\n" + "=" * W)
    all_ok = True
    for key in ["L1", "L2", "L3", "L4"]:
        if key not in results:
            print("  %s  —  （未查）" % key)
            continue
        mark = "通过" if results[key] else "失败"
        if not results[key]:
            all_ok = False
        print("  %s  %s" % (key, mark))
    print("=" * W)
    checked = len(results)
    if all_ok and checked == 4:
        verdict = "四层全绿，项目健康"
    elif all_ok:
        verdict = "已查 %d 层全部通过" % checked
    else:
        verdict = "存在失败项，先修再上线"
    print("结论：%s" % verdict)
    return 0 if all_ok else 1


if __name__ == "__main__":
    sys.exit(main())
