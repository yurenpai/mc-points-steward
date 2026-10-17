#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
test_promo_png.py —— 钉死「手机端宣传图」的三件事：

  1. 数据零手抄 —— 天梯行、总结论（27 = 9 + 18）、现值全部由 fixtures 实算，
     文案只是这些数字的排版，测试锁住数字本身；
  2. 护栏生效 —— 超宽文案必须让渲染函数返回退出码 3，不静默截断；
  3. 产物形态 —— PNG 尺寸/模式正确、品牌色真的画上去了（抽样像素）。

为什么单立一个文件：
    宣传图是对外门面，数字错了是事故；而 Pillow 渲染在无显示环境里
    只有尺寸和像素可断言。本文件是 promo PNG 的唯一回归防线。
"""

import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)                      # skill/
SCRIPTS = os.path.join(ROOT, "scripts")
sys.path.insert(0, SCRIPTS)

import make_promo_png as M  # noqa: E402

PASS = FAIL = 0


def check(name, got, want):
    global PASS, FAIL
    if got == want:
        PASS += 1
        print("  ✓ %s" % name)
    else:
        FAIL += 1
        print("  ✗ %s\n      期望 %r\n      实得 %r" % (name, want, got))


def main():
    data = M.compute()
    stats = M.bucket_stats()
    rows = M.ladder_rows(data)

    print("== 1. 总结论实算（27 = 9 + 18，现值口径） ==")
    check("积分类合计 27", stats["points_total"], 27)
    check("真可兑 9", stats["redeemable"], 9)
    check("绝版 18", stats["extinct"], 18)
    check("每 100 分现值 13.79", data["value_per_100"], 13.79)

    print("== 2. 天梯行结构与实算数字 ==")
    check("六级天梯", [r[0] for r in rows], [24, 50, 100, 200, 500, 800])
    check("解锁件数递增", [r[0] for r in rows if not r[0] == 24] and
          [t["unlocked"] for t in data["tiers"] if not t["is_lottery"]],
          [2, 4, 6, 8, 9])
    check("首行是抽奖档", rows[0][1], "解锁抽奖资格 · 10 品奖池")
    check("抽奖回血 30 分", rows[0][2], "最高回血 30 分")
    check("末行 800 分 9 件", rows[-1][1], "解锁 9 件 · 巨无霸可乐组合")
    check("末行另付 ¥21.9", rows[-1][2], "另付 ¥21.9 起")
    check("100 分档另付 ¥3.9", rows[2][2], "另付 ¥3.9 起")
    # 每行的另付金额必须等于该档 cash_min（不允许文案与数据漂移）
    for r, t in zip(rows, data["tiers"]):
        if t["cash_min"] is not None:
            check("%d 分档另付与 cash_min 一致" % r[0], r[2],
                  "另付 ¥%.1f 起" % t["cash_min"])

    print("== 3. 金拱门采样几何 ==")
    scale, top = 0.5, 40
    pts = M.arch_points(scale, 540, top)
    check("采样点数量 > 50", len(pts) > 50, True)
    # ARCH_PATH 顶点在 path 坐标 y=10，画布顶点 = top + 10*scale
    check("顶点 y = top + 10*scale", min(p[1] for p in pts), top + 10 * scale)
    xs = [p[0] for p in pts]
    check("水平居中（中心 ≈ 540）", abs((min(xs) + max(xs)) / 2 - 540) < 1.5, True)

    print("== 4. 护栏逻辑（不渲染，直接判定） ==")
    probe = M.ImageDraw.Draw(M.Image.new("RGB", (8, 8)))
    f = M.ImageFont.truetype(M.find_font(), 34)
    ok = M.check_fit("t", [("正常宽度", probe.textlength("正常宽度", font=f))], 9999)
    check("正常文本通过", ok, True)
    bad = M.check_fit("t", [("超宽" * 40, probe.textlength("超宽" * 40, font=f))], 100)
    check("超宽文本被拒", bad, False)

    print("== 5. 渲染冒烟（Pillow 实画 + 像素抽查） ==")
    try:
        from PIL import Image
    except ImportError:
        print("  … 跳过（无 Pillow）")
        print("\n%d passed, %d failed" % (PASS, FAIL))
        return 1 if FAIL else 0

    tmp = os.path.join(ROOT, "..", "_archive", "_promo_test")
    os.makedirs(tmp, exist_ok=True)
    v_path = os.path.join(tmp, "v.png")
    s_path = os.path.join(tmp, "s.png")
    rc_v = M.render_vertical(M.find_font(), data, stats, v_path)
    rc_s = M.render_square(M.find_font(), data, stats, s_path)
    check("竖版渲染退出码 0", rc_v, 0)
    check("方版渲染退出码 0", rc_s, 0)

    v = Image.open(v_path)
    s = Image.open(s_path)
    check("竖版尺寸 1080x1440", v.size, (1080, 1440))
    check("方版尺寸 1080x1080", s.size, (1080, 1080))
    check("竖版 RGB 模式", v.mode, "RGB")
    check("方版 RGB 模式", s.mode, "RGB")

    # 品牌色抽查：金色必须出现（金拱门/标题），深色背景必须出现
    def has_color(img, target, tol=12):
        px = img.convert("RGB")
        w, h = px.size
        for yy in range(0, h, 7):
            for xx in range(0, w, 7):
                p = px.getpixel((xx, yy))
                if all(abs(p[i] - target[i]) <= tol for i in range(3)):
                    return True
        return False

    check("竖版含品牌金", has_color(v, M.C_YELLOW_RGB), True)
    check("方版含品牌金", has_color(s, M.C_YELLOW_RGB), True)
    check("竖版含深色背景", has_color(v, (30, 29, 38), 10), True)
    check("方版含深色背景", has_color(s, (30, 29, 38), 10), True)

    print("== 6. 超宽文案必须退出码 3（护栏端到端） ==")
    orig = M.ladder_rows
    M.ladder_rows = lambda d: [(99999, "超" * 60, "超" * 60, M.CORAL_RGB)]
    rc_over = M.render_vertical(M.find_font(), data, stats,
                                os.path.join(tmp, "over.png"))
    M.ladder_rows = orig
    check("超宽文案渲染返回 3", rc_over, 3)

    for p in (v_path, s_path):
        os.remove(p)
    print("\n%d passed, %d failed" % (PASS, FAIL))
    return 1 if FAIL else 0


if __name__ == "__main__":
    sys.exit(main())
