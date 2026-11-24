#!/usr/bin/env python3
"""Export a public-safe snapshot of this governance repo (allowlist + scrub)."""
import argparse
import os
import re
import shutil
import subprocess
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))

ALLOW_FILES = [
    "AGENTS.md",
    "LICENSE",
    ".gitignore",
    ".agents/mcp_config.example.json",
    ".agents/approvals/README.md",
    ".agents/templates/PROJECT_ENV.template.md",
    ".agents/templates/task_plan_template.md",
    ".agents/templates/git-mode.json",
    ".agents/scripts/check_governance.py",
    ".agents/scripts/approval_gate.py",
    ".agents/scripts/verify_governance.py",
    ".agents/scripts/export_public.py",
    ".agents/scripts/requirements.txt",
    ".agents/scripts/gitingest_tool.py",
    ".agents/scripts/skill_curator.py",
    ".agents/scripts/probe_confined.py",
    ".agents/skills/governance-init/SKILL.md",
    ".agents/skills/task-modes/SKILL.md",
    ".agents/skills/init/SKILL.md",
    ".agents/skills/init-agent/SKILL.md",
    ".agents/skills/init-gitvault/SKILL.md",
    "scripts/fetch_vault.py",
    ".githooks/pre-commit",
    ".githooks/commit-msg",
    "scripts/bootstrap_workspace.py",
    "scripts/publish_diagram.py",
    "scripts/build_whitepaper.py",
    "docs/deploy.md",
    "docs/prereqs.md",
    "docs/design/claude-design-system.md",
    "docs/audits/p1-eval-plan.md",
    "docs/audits/evals/README.md",
]
ALLOW_DIRS = [".agents/rules"]
STUBS = {
    "docs/governance-map.md": "# 架构与断点\n\nSTATUS: PLACEHOLDER\nPROJECT_TYPE: 未指定（初始化后必须询问用户，不得默认）\n\n> 占位文件：本工作区的层结构、优先级与已知断点待填。\n\n## 指令链预算\n- 每链 65536，两链合计 131072（DSH 注入预算）。\n",
    "docs/environment-todo.md": "# 执行台账\n\nSTATUS: PLACEHOLDER\n\n> 占位文件：本工作区环境与治理任务的执行状态待填；首轮事实写到 PROJECT_ENV.md。\n",
    "PROJECT_ENV.md": "# PROJECT_ENV — 环境事实\n\n> 模板：安装后由 bootstrap 自动探测，或手工填写。\n\n## 自动探测\n- 仓库根：未知（待填）\n- Python：未知（待填）\n\n## 人工确认（待填）\n- 端口与本地服务：未知（待填）\n- 服务端点与代理：未知（待填）\n- 写入限制/ACL 怪癖：未知（待填）\n- 凭据边界：未知（待填）\n",
    "docs/audits/evals/status.md": "last_run: 2026-01-01\nE1: 未执行\nE2: 未执行\nE3: 未执行\nrecorded_by: template\n",
}
PATH_PAT = r"(?<![A-Za-z0-9_])[A-Za-z]:[\\/](?![\\/])[^\s\x60'\"<>]+"
SCRUB = [
    (re.compile(PATH_PAT), "<path>/..."),
    (re.compile(r"C:[\\/]+Users[\\/]+[A-Za-z0-9_]+"), "%USERPROFILE%"),
]


def head_sha():
    res = subprocess.run(["git", "rev-parse", "--short", "HEAD"], cwd=ROOT,
                         capture_output=True, text=True)
    return res.stdout.strip() or "unknown"


def copy_file(rel, out):
    src, dst = os.path.join(ROOT, rel), os.path.join(out, rel)
    if not os.path.exists(src):
        return "MISSING " + rel
    os.makedirs(os.path.dirname(dst), exist_ok=True)
    shutil.copy2(src, dst)
    return "COPY " + rel


def scrub_file(dst):
    try:
        with open(dst, "r", encoding="utf-8") as fh:
            text = fh.read()
    except UnicodeDecodeError:
        return 0
    hits = 0
    for pattern, repl in SCRUB:
        text, n = pattern.subn(repl, text)
        hits += n
    with open(dst, "w", encoding="utf-8", newline="\n") as fh:
        fh.write(text)
    return hits


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=".tmp/public-export")
    args = ap.parse_args()
    out = os.path.abspath(args.out)
    if os.path.exists(out):
        shutil.rmtree(out)
    os.makedirs(out)

    log = []
    for rel in ALLOW_FILES:
        log.append(copy_file(rel, out))
    for base in ALLOW_DIRS:
        src_dir = os.path.join(ROOT, base)
        for name in sorted(os.listdir(src_dir)):
            if name.endswith(".md"):
                log.append(copy_file(base + "/" + name, out))
    for rel, text in STUBS.items():
        dst = os.path.join(out, rel)
        os.makedirs(os.path.dirname(dst), exist_ok=True)
        with open(dst, "w", encoding="utf-8", newline="\n") as fh:
            fh.write(text)
        log.append("STUB " + rel)

    selfcheck_src = os.path.join(ROOT, ".agents/templates/public-selfcheck.yml")
    if os.path.exists(selfcheck_src):
        dst = os.path.join(out, ".github/workflows/selfcheck.yml")
        os.makedirs(os.path.dirname(dst), exist_ok=True)
        shutil.copy2(selfcheck_src, dst)
        log.append("COPY .github/workflows/selfcheck.yml")

    readme_src = os.path.join(ROOT, ".agents/templates/public-readme.md")
    if os.path.exists(readme_src):
        shutil.copy2(readme_src, os.path.join(out, "README.md"))
        log.append("COPY README.md")

    scrubbed = 0
    for dirpath, _, names in os.walk(out):
        for name in names:
            if name.endswith((".md", ".py", ".sh", ".json", ".gitignore")) or name in ("pre-commit", "commit-msg"):
                scrubbed += scrub_file(os.path.join(dirpath, name))
    with open(os.path.join(out, "VERSION"), "w", encoding="utf-8") as fh:
        fh.write(head_sha() + "\n")
    log.append("VERSION " + head_sha())

    for line in log:
        print(line)
    print("-- files=%d scrub_hits=%d out=%s" % (len(log), scrubbed, out))
    return 0


if __name__ == "__main__":
    sys.exit(main())
