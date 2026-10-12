#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
报告卡 SVG 生成器测试（make_report_svg.py）。

为什么测它：
    这张图是项目的「门面物料」——要发群、要贴 README、要接进演示页。
    它一旦生成失败或数字漂移，外面看到的就是错的。
    这里同时守住两件事：① 生成器不崩、XML 合法；② 关键数字与 fixtures 一致。

运行:
    python tests/test_report_svg.py
"""

import os
import re
import subprocess
import sys
import xml.dom.minidom as minidom

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, ".."))
SCRIPT = os.path.join(ROOT, "scripts", "make_report_svg.py")
OUT = os.path.join(os.path.dirname(ROOT), "assets", "report-card.svg")
PASS, FAIL = 0, 0


def check(name, got, want):
    global PASS, FAIL
    if got == want:
        PASS += 1
        print(f"  ✓ {name}")
    else:
        FAIL += 1
        print(f"  ✗ {name}\n      got={got!r} want={want!r}")


def main():
    print("== 1. 生成器可运行，落盘到 assets/ ==")
    p = subprocess.run([sys.executable, SCRIPT],
                       capture_output=True, text=True, encoding="utf-8")
    check("退出码 0", p.returncode, 0)
    check("输出文件存在", os.path.isfile(OUT), True)
    svg = open(OUT, encoding="utf-8").read()

    print("== 2. XML 合法（发群/贴页面前必须是合法 SVG） ==")
    try:
        minidom.parseString(svg)
        ok = True
    except Exception as e:
        ok = False
        print("     解析失败:", e)
    check("minidom 解析通过", ok, True)

    print("== 3. 关键数字与 fixtures 实算一致 ==")
    check("每 100 积分现值 ¥13.79", "¥13.79" in svg, True)
    check("真可兑 9 件", ">9 件<" in svg, True)
    check("假上架 18 件", ">18 件<" in svg, True)
    check("假上架占比 67%", "占比 67%" in svg, True)
    check("纯积分白拿 0 件", ">0 件<" in svg, True)
    check("漏报率 22%", "漏报率 22%" in svg, True)
    check("性价比差 5.04 倍", "5.04 倍" in svg, True)
    check("最优出口 6.9元可乐麦炫酷", "6.9元可乐麦炫酷" in svg, True)
    check("另付区间 ¥3.9 ~ ¥21.9", "¥3.9 ~ ¥21.9" in svg, True)

    print("== 4. 无障碍与自包含 ==")
    check("有 <title>", "<title>" in svg, True)
    check("有 <desc>", "<desc>" in svg, True)
    # xmlns 命名空间声明不是外部引用；除此之外不应有任何 http 资源或 href
    external = (re.search(r'href\s*=', svg) is not None
                or re.search(r'https?://(?!www\.w3\.org/2000/svg)', svg) is not None)
    check("无外部资源引用（href / 非 xmlns 的 http）", external, False)
    check("viewBox 完整", bool(re.search(r'viewBox="0 0 680 \d+"', svg)), True)

    print("== 5. --stdout 模式不落盘也能输出 ==")
    p2 = subprocess.run([sys.executable, SCRIPT, "--stdout"],
                        capture_output=True, text=True, encoding="utf-8")
    check("退出码 0", p2.returncode, 0)
    check("标准输出是 SVG", p2.stdout.strip().startswith("<svg"), True)

    print(f"\n{'ALL PASS' if FAIL == 0 else 'HAS FAILURE'}  通过 {PASS} / 失败 {FAIL}")
    return 1 if FAIL else 0


if __name__ == "__main__":
    sys.exit(main())
