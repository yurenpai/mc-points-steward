#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
演示 GIF 生成器测试（make_demo_gif.py）。

守两件事：
    ① 生成器可运行、产出是合法 GIF（不是坏文件）；
    ② 选行质量 —— 行数在合理区间、无孤立行、无超宽行溢出画布。
        「选行」是这个脚本唯一的主观环节，也是最容易悄悄退化的地方，
        所以用区间和排除名单把它钉住。

运行:
    python tests/test_demo_gif.py
"""

import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, ".."))
SCRIPT = os.path.join(ROOT, "scripts", "make_demo_gif.py")
OUT = os.path.join(os.path.dirname(ROOT), "assets", "demo.gif")
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
    print("== 1. 生成器可运行（含超宽护栏，退出码 3 = 有行溢出） ==")
    p = subprocess.run([sys.executable, SCRIPT],
                       capture_output=True, text=True, encoding="utf-8")
    check("退出码 0（非 0 即选行或渲染出问题）", p.returncode, 0)
    check("落盘到 assets/demo.gif", os.path.isfile(OUT), True)

    print("== 2. 产出是合法 GIF ==")
    try:
        from PIL import Image
        im = Image.open(OUT)
        ok = im.format == "GIF"
        frames, size = im.n_frames, im.size
    except Exception as e:
        ok, frames, size = False, 0, (0, 0)
        print("     打开失败:", e)
    check("PIL 识别为 GIF", ok, True)
    check("帧数 ≥ 40（打字机效果需要足够帧）", frames >= 40, True)
    check("画布宽度 700", size[0], 700)

    print("== 3. 选行质量 ==")
    sys.path.insert(0, os.path.join(ROOT, "scripts"))
    from make_demo_gif import run_demo, pick_lines, KEY_LINES  # noqa: E402
    lines = pick_lines(run_demo())
    check("选行数 15~40（太少没内容，太多变刷屏）",
          15 <= len(lines) <= 40, True)
    check("三段都在（账本/榜单/抽奖）",
          sum(1 for k in ("积分账本", "真实可兑榜单", "积分抽奖")
              if any(k in l for l in lines)), 3)
    check("无孤立行「② 抽奖回血」",
          any("抽奖回血" in l for l in lines), False)
    check("无超宽行「麦乐鸡-4块」（同名陷阱详情无上下文）",
          any("麦乐鸡-4块" in l for l in lines), False)
    check("关键结论行都在（现值/漏报/隐藏成本）",
          sum(1 for k in ("每 100 积分现值", "默认查询漏报", "纯积分白拿")
              if any(k in l for l in lines)), 3)

    print(f"\n{'ALL PASS' if FAIL == 0 else 'HAS FAILURE'}  通过 {PASS} / 失败 {FAIL}")
    return 1 if FAIL else 0


if __name__ == "__main__":
    sys.exit(main())
