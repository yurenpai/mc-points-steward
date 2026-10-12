#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
麦当劳大赛 · 竞争态势监控
=========================

数据源：GitHub contents API（官方仓库的 RANKING.md）。
不抓 raw.githubusercontent.com —— 该域名在部分网络环境被拦截。

用法：
    python monitor.py                          # 只看榜单概况
    python monitor.py --repo owner/name        # 加上自己的排名与差距
    python monitor.py --repo owner/name --watch   # 每 30 分钟刷新一次（Ctrl+C 退出）

注意 GitHub API 未认证限额 60 次/小时。--watch 模式按 1800 秒间隔轮询，
一小时约 2 次请求，远低于限额；但请勿同时开多个 --watch。

输出全部为客观事实，不含主观建议。
"""

import argparse
import base64
import json
import re
import subprocess
import sys
import time

API = "https://api.github.com"
RANKING_REPO = "M-China/mcd-developer-innovation-challenge"
RANKING_FILE = "RANKING.md"
TIME_RE = re.compile(r"更新时间：(.+?)\s*$", re.M)
ROW_RE = re.compile(r"^\|\s*(\d+)\s*\|\s*([^|]+?)\s*\|\s*[^|]*?\s*\|\s*(\d+)\s*\|\s*$")
MY_REPO_RE = re.compile(r"^[A-Za-z0-9._-]+/[A-Za-z0-9._-]+$")

W = 66


def curl_json(url, retries=2):
    """用 curl 拉 JSON。本机 Python urllib 走代理不稳定，故用 curl 后端。"""
    last = None
    for _ in range(max(1, retries)):
        p = subprocess.run(
            ["curl", "-s", "--max-time", "30", "-H",
             "Accept: application/vnd.github+json", url],
            capture_output=True,
        )
        try:
            return json.loads(p.stdout.decode("utf-8", "replace"))
        except Exception as e:  # noqa: BLE001
            last = e
    raise RuntimeError("请求失败: %s" % last)


def fetch_ranking():
    """取官方排行榜并解析为 [(rank, name, stars), ...]"""
    d = curl_json("%s/repos/%s/contents/%s" % (API, RANKING_REPO, RANKING_FILE))
    if "content" not in d:
        raise RuntimeError("拿不到 RANKING.md: %s" % str(d)[:200])
    txt = base64.b64decode(d["content"]).decode("utf-8", "replace")

    m = TIME_RE.search(txt)
    snap = m.group(1).strip() if m else "未知"

    rows = []
    for line in txt.splitlines():
        mm = ROW_RE.match(line)
        if mm:
            rows.append((int(mm.group(1)), mm.group(2).strip(), int(mm.group(3))))
    if not rows:
        raise RuntimeError("RANKING.md 解析不到任何条目（格式可能变了）")
    return snap, rows


def fetch_stars(repo):
    """查指定仓库的 Star 数。仓库不存在/未推送时返回 None。"""
    try:
        d = curl_json("%s/repos/%s" % (API, repo), retries=1)
        if isinstance(d, dict) and "stargazers_count" in d:
            return int(d["stargazers_count"])
        return None
    except Exception:  # noqa: BLE001
        return None


def bar(title):
    print("=" * W)
    print(title.center(W - 4))
    print("=" * W)


def show(snap, rows, my_repo=None):
    total = len(rows)
    top = rows[0][2]
    line = rows[-1][2]                      # 进榜线 = 榜末 Star 数
    cutoff_rank = rows[-1][0]               # 榜末名次（并列会超过 100）

    bar("麦当劳大赛 · 竞争态势")
    print("榜单快照   : %s" % snap)
    print("榜上项目数 : %d（规则上限 100，并列可超出）" % total)
    print("榜首       : %d Star  (%s)" % (top, rows[0][1]))
    print("第 5 名    : %d Star" % rows[4][2])
    print("进榜线     : %d Star  ← 低于此值不上榜" % line)
    print("榜末名次   : 第 %d 名" % cutoff_rank)

    # 并列密度：进榜线附近挤了多少项目
    packed = sum(1 for _, _, s in rows if s == line)
    print("进榜线并列 : %d 个项目同为 %d Star" % (packed, line))

    if my_repo:
        print("-" * W)
        if not MY_REPO_RE.match(my_repo):
            print("❌ --repo 格式应为 owner/name，收到: %r" % my_repo)
            return
        stars = fetch_stars(my_repo)
        if stars is None:
            print("⚠️ 查不到 %s 的 Star 数。" % my_repo)
            print("   可能原因：仓库还没推送 / 是私有的 / 网络问题。")
            print("   推送并设为 Public 后再跑本脚本。")
            return

        print("我的仓库   : %s" % my_repo)
        print("我的 Star  : %d" % stars)

        if stars >= line:
            # 找自己的名次：比自己星多的项目数 + 1
            above = sum(1 for _, _, s in rows if s > stars)
            my_rank = above + 1
            print("我的名次   : 约第 %d 名  ✅ 已在榜内" % my_rank)
            nxt = [r for r in rows if r[2] > stars]
            if nxt:
                gap = nxt[0][2] - stars
                print("距上一名   : 还差 %d Star（上一名 %d Star）" % (gap, nxt[0][2]))
        else:
            print("我的名次   : ❌ 未进榜（0 Star 项目不进入排行榜）")
            print("进榜还差   : %d Star" % (line - stars))

    print("=" * W)


def main():
    ap = argparse.ArgumentParser(description="麦当劳大赛竞争态势监控")
    ap.add_argument("--repo", help="自己的仓库，格式 owner/name")
    ap.add_argument("--watch", action="store_true",
                    help="每 1800 秒刷新一次（一小时约 2 次请求，低于 API 限额）")
    ap.add_argument("--interval", type=int, default=1800,
                    help="--watch 的轮询间隔秒数，默认 1800")
    args = ap.parse_args()

    if args.watch:
        print("监控模式：每 %d 秒刷新，Ctrl+C 退出\n" % args.interval)
    while True:
        try:
            snap, rows = fetch_ranking()
            show(snap, rows, args.repo)
        except Exception as e:  # noqa: BLE001
            print("⚠️ 本次拉取失败: %s" % e)
            print("   （GitHub API 未认证限额 60 次/小时，撞限额就等一小时）")
        if not args.watch:
            break
        print("\n[%s] 等待 %d 秒..." % (time.strftime("%H:%M:%S"), args.interval))
        try:
            time.sleep(args.interval)
        except KeyboardInterrupt:
            print("\n已退出。")
            break


if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        sys.exit(0)
