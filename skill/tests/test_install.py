#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
B1 冒烟验证：把 skill/ 安装到本机 WorkBuddy skills 目录并检查可加载性。

检查项：
  1. frontmatter 可被解析（name / description 合规）
  2. 目录内相对路径引用（references/ scripts/ tests/fixtures/）全部解析得到
  3. SKILL.md 正文里出现的脚本路径真实存在
  4. 安装后脚本仍可执行（以安装目录为 cwd 跑一次 demo.py --section 1）

用法：
    python tests/test_install.py                 # 仅校验源目录
    python tests/test_install.py --install       # 校验 + 安装到 ~/.workbuddy/skills/
    python tests/test_install.py --install --smoke   # 校验 + 安装 + 跑一次脚本
"""

import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

SRC = Path(__file__).resolve().parent.parent          # skill/
INSTALL_ROOT = Path.home() / ".workbuddy" / "skills"
INSTALL_DIR = INSTALL_ROOT / "mc-points-steward"

PY = sys.executable

results = []


def check(label, ok, detail=""):
    results.append((label, ok, detail))
    print(f"  [{'OK ' if ok else 'FAIL'}] {label}" + (f"  {detail}" if detail else ""))
    return ok


def validate_frontmatter(skill_md: Path):
    content = skill_md.read_text(encoding="utf-8")
    if not content.startswith("---"):
        return False, "缺少 YAML frontmatter"
    m = re.match(r"^---\n(.*?)\n---", content, re.DOTALL)
    if not m:
        return False, "frontmatter 格式非法"
    fm = m.group(1)

    for key in ("name:", "description:"):
        if key not in fm:
            return False, f"缺少字段 {key}"

    name = re.search(r"name:\s*(.+)", fm).group(1).strip()
    if not re.match(r"^[a-z0-9-]+$", name):
        return False, f"name '{name}' 不符合 hyphen-case"
    if name.startswith("-") or name.endswith("-") or "--" in name:
        return False, f"name '{name}' 首尾或连续连字符非法"

    # description 可能是折叠多行，取到下一个顶层 key 为止
    desc_block = re.search(r"description:\s*(.*?)(?=\n[a-z_]+:)", fm, re.DOTALL)
    desc = desc_block.group(1) if desc_block else ""
    if "<" in desc or ">" in desc:
        return False, "description 不能含尖括号"
    if len(desc.strip()) < 20:
        return False, f"description 过短（{len(desc.strip())} 字符），触发词命中率低"

    return True, f"name={name}, description {len(desc.strip())} 字符"


def main():
    do_install = "--install" in sys.argv
    do_smoke = "--smoke" in sys.argv

    print("=" * 60)
    print("B1 · Skill 加载冒烟验证")
    print("=" * 60)

    # --- 1. frontmatter ---
    print("\n[1] frontmatter 解析")
    ok, detail = validate_frontmatter(SRC / "SKILL.md")
    check("SKILL.md frontmatter", ok, detail)

    # --- 2. 相对路径引用 ---
    print("\n[2] 相对路径引用解析")
    for rel in ["references/api_fields.md", "references/templates.md",
                "scripts/rank_products.py", "scripts/lottery_advice.py",
                "scripts/demo.py",
                "tests/fixtures/account_20261012.json",
                "tests/fixtures/mall_products_20261012.json",
                "tests/fixtures/lottery_info_20261012.json"]:
        check(rel, (SRC / rel).exists())

    # --- 3. SKILL.md 正文提到的脚本路径 ---
    print("\n[3] SKILL.md 正文引用的路径")
    body = (SRC / "SKILL.md").read_text(encoding="utf-8")
    mentioned = set(re.findall(r"(?:scripts|references|tests)/[A-Za-z0-9_./-]+", body))
    for rel in sorted(mentioned):
        rel = rel.rstrip(".")
        check(f"正文引用 -> {rel}", (SRC / rel).exists())

    # --- 4. 安装 ---
    if do_install:
        print(f"\n[4] 安装到 {INSTALL_DIR}")
        INSTALL_ROOT.mkdir(parents=True, exist_ok=True)
        if INSTALL_DIR.exists():
            shutil.rmtree(INSTALL_DIR)
        shutil.copytree(SRC, INSTALL_DIR)
        check("复制目录", (INSTALL_DIR / "SKILL.md").exists())
        ok2, d2 = validate_frontmatter(INSTALL_DIR / "SKILL.md")
        check("安装后 frontmatter 仍合规", ok2, d2)
        n = sum(1 for _ in INSTALL_DIR.rglob("*") if _.is_file())
        check("文件搬运完整", n >= 11, f"{n} 个文件")

        if do_smoke:
            print("\n[5] 安装目录内跑脚本（模拟 Skill 被加载后的执行环境）")
            for sec, label in [(1, "账本"), (2, "榜单"), (3, "抽奖")]:
                r = subprocess.run(
                    [PY, str(INSTALL_DIR / "scripts" / "demo.py"), "--section", str(sec)],
                    capture_output=True, text=True, encoding="utf-8", errors="replace",
                    cwd=str(INSTALL_DIR),
                )
                check(f"demo.py --section {sec} ({label})",
                      r.returncode == 0 and len(r.stdout.strip()) > 100,
                      f"exit={r.returncode}, {len(r.stdout)} 字符")
            r = subprocess.run(
                [PY, str(INSTALL_DIR / "scripts" / "rank_products.py"),
                 "--input", str(INSTALL_DIR / "tests" / "fixtures" / "mall_products_20261012.json")],
                capture_output=True, text=True, encoding="utf-8", errors="replace",
                cwd=str(INSTALL_DIR),
            )
            check("rank_products.py", r.returncode == 0, f"exit={r.returncode}")

    # --- 汇总 ---
    print("\n" + "=" * 60)
    failed = [r for r in results if not r[1]]
    print(f"总计 {len(results)} 项，通过 {len(results) - len(failed)}，失败 {len(failed)}")
    if failed:
        for label, _, detail in failed:
            print(f"  FAIL: {label}  {detail}")
    print("=" * 60)
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
