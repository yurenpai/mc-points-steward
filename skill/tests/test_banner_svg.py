#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
品牌横幅 SVG 生成器测试（make_banner_svg.py）。

为什么测它：
    banner.svg 是 README 首屏门面，也是三张物料里传播效率最高的一张。
    它有两个脆弱点：① 数字漂移（图文不一致比没图更糟）；② 布局越界
    （文字压出画布、pill 重叠）。这里同时守住：生成不崩、XML 合法、
    关键数字与 fixtures 一致、品牌元素齐全、无外部资源依赖。

运行:
    python tests/test_banner_svg.py
"""

import os
import re
import subprocess
import sys
import xml.dom.minidom as minidom

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, ".."))
SCRIPT = os.path.join(ROOT, "scripts", "make_banner_svg.py")
OUT = os.path.join(os.path.dirname(ROOT), "assets", "banner.svg")
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

    print("== 2. XML 合法 ==")
    try:
        minidom.parseString(svg)
        ok = True
    except Exception as e:
        ok = False
        print("     解析失败:", e)
    check("minidom 解析通过", ok, True)

    print("== 3. 关键数字与 fixtures 实算一致（零手抄） ==")
    check("假上架率 67%", ">67%<" in svg, True)
    check("假上架 18 件", "件名存实亡" in svg and "· 18" in svg, True)
    check("纯积分白拿 0 件", ">0 件<" in svg, True)
    check("到店另付 9 件", "件需到店另付" in svg and "· 9" in svg, True)
    check("默认查询漏报 2 件", ">2 件<" in svg, True)
    check("标称上架 27 件", "件标称上架" in svg and "· 27" in svg, True)

    print("== 4. 品牌元素齐全 ==")
    check("深棕渐变背景", 'id="bg"' in svg and "#1a0d08" in svg, True)
    check("麦当劳金 #FFC72C", "#FFC72C" in svg, True)
    check("麦当劳红 #DA291C", "#DA291C" in svg, True)
    check("金拱门 M（path 手绘）", "M 10 92 C 10 22 26 10 42 10" in svg, True)
    check("金色辉光滤镜", 'id="glow"' in svg, True)
    check("主标题 麦享掌柜", ">麦享掌柜<" in svg, True)
    check("英文名 mc-points-steward", ">mc-points-steward<" in svg, True)
    check("赛事行", "麦当劳中国 MCP 开发者创新大赛" in svg, True)

    print("== 5. 布局不越界（画布 680x300） ==")
    # 负向后视：排除 cy/xy/by/ry 等以 y 结尾的属性名
    ys = [float(v) for v in re.findall(r'(?<![a-zA-Z-])y="(\d+(?:\.\d+)?)"', svg)]
    check("最大 y <= 298（pill 底 278 + 余量）", max(ys) <= 298, True)
    xs = [float(v) for v in re.findall(r'(?<![a-zA-Z-])x="(\d+(?:\.\d+)?)"', svg)]
    check("最大 x <= 680", max(xs) <= 680, True)
    check("三个 pill 矩形", svg.count('rx="10"'), 3)
    check("viewBox 完整", bool(re.search(r'viewBox="0 0 680 300"', svg)), True)

    print("== 6. 无障碍与自包含 ==")
    check("有 <title>", "<title>" in svg, True)
    check("有 <desc>", "<desc>" in svg, True)
    check("无 %% 格式化残留", "%%" in svg, False)
    external = (re.search(r'href\s*=', svg) is not None
                or re.search(r'https?://(?!www\.w3\.org/2000/svg)', svg) is not None)
    check("无外部资源引用", external, False)

    print("== 7. --stdout 模式不落盘也能输出 ==")
    p2 = subprocess.run([sys.executable, SCRIPT, "--stdout"],
                        capture_output=True, text=True, encoding="utf-8")
    check("退出码 0", p2.returncode, 0)
    check("标准输出是 SVG", p2.stdout.strip().startswith("<svg"), True)

    print(f"\n{'ALL PASS' if FAIL == 0 else 'HAS FAILURE'}  通过 {PASS} / 失败 {FAIL}")
    return 1 if FAIL else 0


if __name__ == "__main__":
    sys.exit(main())
