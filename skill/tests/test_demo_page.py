#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
在线演示页测试（make_demo_page.py → docs/index.html）。

守三件事：
    ① 页面能生成、结构完整（标题/SVG/三段 pre/GIF 引用都在）；
    ② 自包含 —— 除了本地化的 assets/demo.gif，不得有任何外部 src/href
       （GitHub Pages 以 docs/ 为根，`../assets/` 会 404，这是踩过的坑）；
    ③ 无占位符残留 —— __SVG__ 之类漏替换会直接暴露给访客。

运行:
    python tests/test_demo_page.py
"""

import os
import re
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, ".."))
SCRIPT = os.path.join(ROOT, "scripts", "make_demo_page.py")
REPO = os.path.dirname(ROOT)
PAGE = os.path.join(REPO, "docs", "index.html")
GIF = os.path.join(REPO, "docs", "assets", "demo.gif")
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
    print("== 1. 生成器可运行 ==")
    p = subprocess.run([sys.executable, SCRIPT],
                       capture_output=True, text=True, encoding="utf-8")
    check("退出码 0", p.returncode, 0)
    check("docs/index.html 存在", os.path.isfile(PAGE), True)
    page = open(PAGE, encoding="utf-8").read()

    print("== 2. 结构完整 ==")
    check("有 DOCTYPE", page.lstrip().startswith("<!DOCTYPE html>"), True)
    check("charset utf-8", 'charset="utf-8"' in page, True)
    check("viewport（移动端可看）", 'name="viewport"' in page, True)
    check("内联了报告卡 SVG", page.count("<svg") >= 1, True)
    check("内联了品牌横幅 SVG", page.count("<svg") >= 2, True)
    check("横幅含金拱门 path", "M 10 92 C 10 22 26 10 42 10" in page, True)
    check("横幅含三个实测 pill", "假上架率" in page and "默认查询漏报" in page, True)
    check("三段输出都在",
          sum(1 for k in ("W1 · 积分账本", "W2 · 积分商城", "W3 · 积分抽奖")
              if k in page), 3)
    check("GIF 已本地化到 docs/assets/", os.path.isfile(GIF), True)

    print("== 3. 自包含（GitHub Pages 以 docs/ 为根） ==")
    refs = re.findall(r'(?:src|href)="([^"]+)"', page)
    external = [r for r in refs if r.startswith(("http://", "https://", "../", "/"))]
    check("无外部/越界引用", external, [])
    check("唯一引用是本地 GIF", sorted(set(refs)), ["assets/demo.gif"])

    print("== 4. 无占位符残留 ==")
    left = sum(page.count("__%s__" % k) for k in ("SVG", "SEC1", "SEC2", "SEC3"))
    check("__SVG__/__SEC*__ 全部替换", left, 0)

    print("== 5. 内容真实（非手抄占位） ==")
    check("含实测现值 ¥13.79", "¥13.79" in page, True)
    check("含 27 件在售口径", "27 件在售" in page, True)
    check("含纯积分白拿 0 件结论", "纯积分白拿" in page, True)

    print(f"\n{'ALL PASS' if FAIL == 0 else 'HAS FAILURE'}  通过 {PASS} / 失败 {FAIL}")
    return 1 if FAIL else 0


if __name__ == "__main__":
    sys.exit(main())
