#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
make_demo_page.py —— 生成静态在线演示页 docs/index.html。

为什么放 docs/：
    前 10 名中 5 个有在线演示页（GitHub Pages / 在线地图 / 在线试算）。
    GitHub Pages 默认从 `/docs` 提供静态文件（Settings → Pages → Branch: main,
    folder: /docs），所以页面放这里，开箱即可部署，不需要额外构建。

自包含原则（重要）：
    GitHub Pages 的站内相对路径以 docs/ 为根，`../assets/xxx` 会 404。
    因此本页面把三样东西全部内联/本地化：
      1. report-card.svg  —— 代码直接内联进 HTML，无路径依赖；
      2. demo.gif          —— 复制一份到 docs/assets/demo.gif；
      3. demo.py 输出     —— subprocess 实跑后转义进 <pre>，文字未改。
    产物 docs/ 目录可整体扔到任何静态服务器（包括本地 file:// 打开）。

用法:
    python make_demo_page.py              # 生成 docs/index.html
    python make_demo_page.py --open       # 生成后用默认浏览器打开（本地预览）
"""

import argparse
import html
import os
import shutil
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
SKILL = os.path.dirname(HERE)
REPO = os.path.dirname(SKILL)
DOCS = os.path.join(REPO, "docs")
ASSETS = os.path.join(REPO, "assets")


def run_demo(section=None):
    cmd = [sys.executable, os.path.join(HERE, "demo.py")]
    if section:
        cmd += ["--section", str(section)]
    p = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8")
    if p.returncode != 0:
        raise RuntimeError("demo.py 运行失败: %s" % p.stderr[:300])
    return p.stdout


def read_svg():
    path = os.path.join(ASSETS, "report-card.svg")
    if not os.path.isfile(path):
        raise RuntimeError("找不到 %s，先跑 make_report_svg.py" % path)
    with open(path, encoding="utf-8") as f:
        return f.read()


def read_banner():
    path = os.path.join(ASSETS, "banner.svg")
    if not os.path.isfile(path):
        raise RuntimeError("找不到 %s，先跑 make_banner_svg.py" % path)
    with open(path, encoding="utf-8") as f:
        return f.read()


def build():
    svg = read_svg()
    # SVG 内联进 HTML：去掉 XML 声明（若有），其余原样嵌入
    if svg.lstrip().startswith("<?xml"):
        svg = svg[svg.index("?>") + 2:].lstrip()

    banner = read_banner()
    if banner.lstrip().startswith("<?xml"):
        banner = banner[banner.index("?>") + 2:].lstrip()

    sec1 = html.escape(run_demo(1))
    sec2 = html.escape(run_demo(2))
    sec3 = html.escape(run_demo(3))

    page = """<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>麦享掌柜 · mc-points-steward — 积分资产管家（在线演示）</title>
<meta name="description" content="麦当劳中国 MCP 开发者创新大赛参赛作品。查得清账、剔得掉假、算得出值、守得住手。">
<style>
  :root {
    --red: #993C1D; --red-bright: #DA291C; --yellow: #FFC72C;
    --ink: #26215C; --text: #2C2C2A; --sub: #888780;
    --line: #E4E1D8; --card: #FAF6EF; --bg: #FFFFFF;
  }
  * { box-sizing: border-box; }
  body {
    margin: 0; background: var(--bg); color: var(--text);
    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', 'PingFang SC',
                 'Microsoft YaHei', sans-serif;
    line-height: 1.65;
  }
  .wrap { max-width: 860px; margin: 0 auto; padding: 48px 24px 80px; }
  header { border-bottom: 3px solid var(--yellow); padding-bottom: 24px; margin-bottom: 32px; }
  h1 { font-size: 30px; margin: 0 0 8px; color: var(--ink); }
  .tagline { color: var(--sub); font-size: 15px; margin: 0; }
  .badges { margin-top: 14px; }
  .badge {
    display: inline-block; font-size: 12px; padding: 3px 10px; margin-right: 8px;
    border-radius: 999px; background: var(--card); color: var(--ink);
    border: 1px solid var(--line);
  }
  h2 { font-size: 20px; color: var(--ink); margin: 44px 0 6px; }
  h2 .num { color: var(--red); font-variant-numeric: tabular-nums; margin-right: 8px; }
  .hint { color: var(--sub); font-size: 13.5px; margin: 0 0 18px; }
  .card-svg { margin: 24px 0 8px; }
  .card-svg svg { display: block; width: 100%; height: auto;
                  border: 1px solid var(--line); border-radius: 10px; }
  .banner-svg { margin: 0 0 28px; }
  .banner-svg svg { display: block; width: 100%; height: auto;
                    border-radius: 10px; box-shadow: 0 2px 14px rgba(26,13,8,.18); }
  figure { margin: 24px 0; }
  figure img { width: 100%; border: 1px solid var(--line); border-radius: 10px; }
  figcaption { color: var(--sub); font-size: 12.5px; text-align: center; margin-top: 8px; }
  pre {
    background: #1E1D26; color: #E8E6DF; border-radius: 10px;
    padding: 18px 20px; overflow-x: auto; font-size: 13px; line-height: 1.55;
    font-family: 'DengXian', 'Consolas', 'SF Mono', Menlo, monospace;
  }
  table { width: 100%; border-collapse: collapse; font-size: 14px; margin: 16px 0; }
  th, td { text-align: left; padding: 9px 12px; border-bottom: 1px solid var(--line); }
  th { color: var(--ink); font-weight: 600; background: var(--card); }
  td.num { text-align: right; font-variant-numeric: tabular-nums; }
  .warn { color: var(--red-bright); font-weight: 600; }
  .ok { color: #2F6B3C; font-weight: 600; }
  .note {
    background: var(--card); border-left: 4px solid var(--yellow);
    padding: 14px 18px; border-radius: 0 8px 8px 0; font-size: 14px; margin: 20px 0;
  }
  code { background: var(--card); padding: 2px 6px; border-radius: 4px; font-size: 13px; }
  pre code { background: none; padding: 0; }
  footer { margin-top: 56px; padding-top: 20px; border-top: 1px solid var(--line);
           color: var(--sub); font-size: 12.5px; }
  a { color: var(--red); }
</style>
</head>
<body>
<div class="wrap">

<header>
  <h1>麦享掌柜 · mc-points-steward</h1>
  <p class="tagline">一个替你打理麦当劳积分资产的 WorkBuddy Skill ——
     <strong>查得清账、剔得掉假、算得出值、守得住手</strong>。</p>
  <div class="badges">
    <span class="badge">麦当劳中国 MCP 开发者创新大赛</span>
    <span class="badge">WorkBuddy Skill</span>
    <span class="badge">纯 Python 标准库</span>
    <span class="badge">MIT</span>
  </div>
</header>

<div class="banner-svg">
__BANNER__
</div>

<div class="note">
  <strong>本页是什么：</strong>这是作品的<strong>离线在线演示</strong>——
  所有数字来自 2026-10-12 对麦当劳官方 MCP 的真实调用快照，
  由脚本自动渲染，<strong>无需 Token、无需安装</strong>即可看到完整效果。
  真实使用时连接 <code>mcd-mcp</code> 即可获取实时数据。
</div>

<h2><span class="num">01</span>一图看懂：积分资产体检报告</h2>
<p class="hint">这张图不是手工绘制的，是 <code>make_report_svg.py</code> 从真实调用快照实算生成。</p>
<div class="card-svg">
__SVG__
</div>

<h2><span class="num">02</span>动态演示：完整跑一遍</h2>
<p class="hint">终端风录屏，文字与 <code>python scripts/demo.py</code> 实际输出逐字一致。</p>
<figure>
  <img src="assets/demo.gif" alt="麦享掌柜离线演示：积分账本、真实可兑榜单、抽奖参谋">
  <figcaption>离线演示 · 数据快照 2026-10-12 · 账户 ID 已脱敏</figcaption>
</figure>

<h2><span class="num">03</span>三段输出原文</h2>
<p class="hint">与 Skill 真实运行时的输出格式完全一致（此处为离线快照）。</p>

<h2 style="font-size:16px;margin-top:28px">W1 · 积分账本</h2>
<pre>__SEC1__</pre>

<h2 style="font-size:16px;margin-top:28px">W2 · 积分商城真实可兑榜单</h2>
<pre>__SEC2__</pre>

<h2 style="font-size:16px;margin-top:28px">W3 · 积分抽奖参谋</h2>
<pre>__SEC3__</pre>

<h2><span class="num">04</span>它挖出了三个官方接口不会告诉你的问题</h2>
<table>
  <tr><th>问题</th><th>实测结论</th><th>后果</th></tr>
  <tr>
    <td><strong>假上架</strong></td>
    <td>27 件标 <code>status=2</code> 的积分类商品中，<span class="warn">18 件</span>的下架时间早已过去</td>
    <td>货架 67% 是名存实亡的</td>
  </tr>
  <tr>
    <td><strong>隐藏现金成本</strong></td>
    <td>9 件真可兑商品，<span class="warn">0 件</span>是纯积分白拿（<code>extTradePrice</code> 只在详情接口）</td>
    <td>「100 分换冰淇淋」实为 100 分 + ¥3.9</td>
  </tr>
  <tr>
    <td><strong>默认查询漏报</strong></td>
    <td>不传 <code>catRuleIds</code> 会少返回 <span class="warn">2 件</span>真能兑的商品</td>
    <td>漏报率 22%</td>
  </tr>
</table>

<h2><span class="num">05</span>安全边界</h2>
<p>涉及不可逆操作（兑换下单 <code>mall-create-order</code>、抽奖 <code>draw-lottery</code>）时，
Skill 一定先把<strong>商品名、积分、有效期、到店另付金额</strong>摆出来，
等你明确说「确认」才动手。资格判定只信官方的 <code>drawDecision</code>，
不由积分余额自行推断。</p>

<footer>
  <p>数据来源：麦当劳中国 MCP（<code>mcp.mcd.cn</code>）真实调用快照，2026-10-12。<br>
  本页由 <code>make_demo_page.py</code> 自动生成 · 麦享掌柜 mc-points-steward · MIT License ·
  非麦当劳官方产品。</p>
</footer>

</div>
</body>
</html>
"""
    page = (page.replace("__SVG__", svg)
                .replace("__BANNER__", banner)
                .replace("__SEC1__", sec1)
                .replace("__SEC2__", sec2)
                .replace("__SEC3__", sec3))
    return page


def main():
    ap = argparse.ArgumentParser(description="生成静态在线演示页 docs/index.html")
    ap.add_argument("--open", action="store_true", help="生成后用默认浏览器打开")
    args = ap.parse_args()

    page = build()

    os.makedirs(DOCS, exist_ok=True)
    # GIF 本地化：GitHub Pages 的 docs/ 为根，无法引用 ../assets/
    os.makedirs(os.path.join(DOCS, "assets"), exist_ok=True)
    gif_src = os.path.join(ASSETS, "demo.gif")
    gif_dst = os.path.join(DOCS, "assets", "demo.gif")
    if os.path.isfile(gif_src):
        shutil.copyfile(gif_src, gif_dst)

    out = os.path.join(DOCS, "index.html")
    with open(out, "w", encoding="utf-8") as f:
        f.write(page)

    print("已生成 %s（%d 字节）" % (out, len(page.encode("utf-8"))))
    print("GIF 副本 %s（%d 字节）" % (gif_dst, os.path.getsize(gif_dst)))
    print("部署：GitHub 仓库 Settings → Pages → Branch: main · folder: /docs → Save")

    if args.open:
        import webbrowser
        webbrowser.open("file://" + os.path.abspath(out))
    return 0


if __name__ == "__main__":
    sys.exit(main())
