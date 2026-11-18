#!/usr/bin/env python3
"""Verify that a workspace's governance stack is actually wired."""
import argparse
import glob
import io
import json
import os
import re
import subprocess
import sys
import urllib.request

FAIL, WARN, OK = [], [], []


def add(level, msg):
    {"FAIL": FAIL, "WARN": WARN, "OK": OK}[level].append(msg)


def read(path):
    with io.open(path, "r", encoding="utf-8", errors="replace") as f:
        return f.read()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--target", required=True)
    ap.add_argument("--strict", action="store_true")
    ap.add_argument("--require-external", action="store_true", help="外部依赖缺失按 FAIL 处理")
    ap.add_argument("--print-remedies", action="store_true", help="对 WARN/FAIL 项打印修复入口")
    args = ap.parse_args()
    t = os.path.abspath(args.target)

    checker = os.path.join(t, ".agents", "scripts", "check_governance.py")
    if not os.path.exists(checker):
        add("FAIL", "缺 .agents/scripts/check_governance.py")
    else:
        text = read(checker)
        for marker in ("RULE_META", "EVAL_STATUS", "approval_gate.py"):
            add("OK" if marker in text else "FAIL", "checker %s" % marker)

    gate = os.path.join(t, ".agents", "scripts", "approval_gate.py")
    add("OK" if os.path.exists(gate) else "FAIL", "approval_gate.py")

    pre = os.path.join(t, ".githooks", "pre-commit")
    if os.path.exists(pre):
        add("OK" if "approval_gate.py" in read(pre) else "FAIL", "pre-commit 调用 approval_gate")
    else:
        add("FAIL", "缺 .githooks/pre-commit")

    rules_dir = os.path.join(t, ".agents", "rules")
    rules = sorted(f for f in os.listdir(rules_dir) if f.endswith(".md")) if os.path.isdir(rules_dir) else []
    add("OK" if len(rules) >= 14 else "FAIL", "rules 数量=%d（应≥14）" % len(rules))
    missing_meta = [f for f in rules if not read(os.path.join(rules_dir, f)).lstrip("\ufeff").startswith("---")]
    if missing_meta:
        add("FAIL", "缺 frontmatter：%s" % ",".join(missing_meta[:4]))

    if os.path.isdir(os.path.join(t, ".git")):
        res = subprocess.run(["git", "config", "--get", "core.hooksPath"], cwd=t,
                             capture_output=True, text=True)
        hp = (res.stdout or "").strip()
        add("OK" if hp == ".githooks" else "FAIL", "core.hooksPath=%s" % (hp or "未设置"))

    for rel in (".agents/approvals/README.md", "docs/audits/evals/status.md", "PROJECT_ENV.md"):
        add("OK" if os.path.exists(os.path.join(t, rel)) else "WARN", rel)

    env_path = os.path.join(t, "PROJECT_ENV.md")
    if os.path.exists(env_path):
        env_text = read(env_path)
        unknown = env_text.count("未知（待填）")
        placeholders = len(re.findall(r"<[\u4e00-\u9fff][^>\n]{0,12}>", env_text))
        if unknown or placeholders:
            add("WARN", "PROJECT_ENV 未填：未知=%d 占位=%d" % (unknown, placeholders))

    backups = glob.glob(os.path.join(t, ".agents.bak-*"))
    if backups:
        add("WARN", "目标仓内存在备份目录 %d 个（建议放父目录 .gov-backups）" % len(backups))

    status = os.path.join(t, "docs", "audits", "evals", "status.md")
    if os.path.exists(status):
        fields = dict(re.findall(r"^(last_run|E1|E2|E3|recorded_by)\s*:\s*(.+)$", read(status), re.M))
        add("OK" if len(fields) >= 5 else "FAIL", "evals/status 字段=%d" % len(fields))

    cc = os.path.join(os.path.expanduser("~"), ".cc-safety-net", "rules", "rule.json")
    if os.path.exists(cc):
        add("OK", "cc-safety-net 用户策略")
    else:
        add("FAIL" if args.require_external else "WARN",
            "缺 cc-safety-net 用户策略：%s（裸 git 不会被拦）" % cc)
    try:
        urllib.request.urlopen("http://127.0.0.1:8765/api/status", timeout=2)
        add("OK", "git-vault 网关可达")
    except Exception:
        add("FAIL" if args.require_external else "WARN",
            "git-vault 网关不可达（http://127.0.0.1:8765/api/status；提交通道未就绪）")

    for rel in ("docs/governance-map.md", "docs/environment-todo.md"):
        path = os.path.join(t, rel)
        if not os.path.exists(path):
            continue
        body = read(path)
        if "STATUS: PLACEHOLDER" in body:
            add("WARN", "占位未填：%s" % rel)
        if "PROJECT_TYPE: 未指定" in body:
            add("WARN", "项目类型未询问：%s（初始化结束后必须问用户，不得默认）" % rel)

    remedies = [
        ("cc-safety-net", "安装/配置拦截器：策略文件应在 ~/.cc-safety-net/rules/rule.json；见 docs/prereqs.md"),
        ("git-vault", "启动网关：<path>/... http://127.0.0.1:8765/api/status 返回 200；见 docs/prereqs.md"),
        ("PROJECT_ENV", "补 PROJECT_ENV.md 的未知项，或重跑 bootstrap 让其重新探测"),
        ("占位未填", "补 docs/governance-map.md 与 docs/environment-todo.md，或重跑 bootstrap --force"),
        ("备份目录", "把备份移到父目录：--clean 默认已外置；已有备份可手工 mv 或 --purge-backups"),
        ("provenance", "见 docs/prereqs.md"),
    ]
    if args.print_remedies:
        shown = [advice for key, advice in remedies if any(key in item for item in WARN + FAIL)]
        if shown:
            print("--- remedies ---")
            for advice in shown:
                print("- %s" % advice)

    for level, items in (("OK", OK), ("WARN", WARN), ("FAIL", FAIL)):
        for msg in items:
            print("[%s] %s" % (level, msg))
    print("verify: ok=%d warn=%d fail=%d" % (len(OK), len(WARN), len(FAIL)))
    if FAIL or (args.strict and WARN):
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
