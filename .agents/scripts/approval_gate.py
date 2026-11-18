#!/usr/bin/env python3
"""Pre-commit approval gate: high-risk staged changes require a receipt."""
import os
import re
import subprocess
import sys

PROTECTED = ("AGENTS.md", ".agents/rules/", ".agents/scripts/check_governance.py",
             ".agents/scripts/approval_gate.py", ".githooks/")
DEPENDENCY = (".agents/scripts/requirements.txt", "package.json", "package-lock.json",
              "pnpm-lock.yaml", "pyproject.toml", "poetry.lock")
GATE = (".githooks/", ".agents/scripts/check_governance.py", ".agents/scripts/approval_gate.py")
RECEIPT_DIR = ".agents/approvals/"
CATEGORIES = ("deletion", "protected-change", "dependency", "gate-change")
REQUIRED_FIELDS = ("category", "targets", "impact", "rollback", "approver", "date")


def git(*args):
    return subprocess.run(["git"] + list(args), capture_output=True, text=True,
                          encoding="utf-8", errors="replace")


def have_head():
    return git("rev-parse", "--verify", "HEAD").returncode == 0


def staged_entries():
    res = git("diff", "--cached", "--name-status", "-M")
    if res.returncode != 0:
        return None
    entries = []
    for line in res.stdout.splitlines():
        parts = line.split("\t")
        if len(parts) >= 2:
            entries.append((parts[0], parts[1], parts[2] if len(parts) > 2 else ""))
    return entries


def under(path, prefixes):
    return any(path == p or path.startswith(p) for p in prefixes)


def parse_receipts(staged):
    receipts = {}
    for status, path, _ in staged:
        if not path.startswith(RECEIPT_DIR) or not path.endswith(".md"):
            continue
        if not os.path.exists(path):
            continue
        fields = {}
        with open(path, "r", encoding="utf-8", errors="replace") as fh:
            for line in fh:
                m = re.match(r"^\s*([a-z_]+)\s*:\s*(.+?)\s*$", line)
                if m:
                    fields[m.group(1)] = m.group(2)
        missing = [f for f in REQUIRED_FIELDS if not fields.get(f)]
        if missing:
            print("approval_gate: %s 缺字段 %s" % (path, ",".join(missing)))
            continue
        if fields["category"] not in CATEGORIES:
            print("approval_gate: %s 的 category 非法：%s" % (path, fields["category"]))
            continue
        receipts.setdefault(fields["category"], []).append(path)
    return receipts


def main() -> int:
    if not have_head():
        print("approval_gate: 仓库尚无提交（初始导入），跳过收据门禁")
        return 0
    staged = staged_entries()
    if staged is None:
        print("approval_gate: 无法读取 staged diff（仓库异常），拒绝提交")
        return 1
    if not staged:
        return 0

    required = {}
    deleted = [path for status, path, _ in staged if status.startswith("D")]
    for path in deleted:
        if under(path, PROTECTED):
            required.setdefault("deletion", []).append(path)
    if len(deleted) >= 2:
        required.setdefault("deletion", []).extend(deleted)
    for status, path, _ in staged:
        if status.startswith(("A", "D")) or not os.path.exists(path):
            continue
        if under(path, PROTECTED):
            required.setdefault("protected-change", []).append(path)
        if under(path, DEPENDENCY):
            required.setdefault("dependency", []).append(path)
        if under(path, GATE):
            required.setdefault("gate-change", []).append(path)

    if not required:
        return 0

    receipts = parse_receipts(staged)
    missing = [cat for cat in required if cat not in receipts]
    if not missing:
        return 0
    print("approval_gate: 本次提交命中高风险类别，缺少同次提交的审批收据：")
    for cat in missing:
        print("  - %s: %s" % (cat, ", ".join(sorted(set(required[cat]))[:6])))
    print("请按 .agents/approvals/README.md 写收据并一并暂存；收据只证明批准存在。")
    return 1


if __name__ == "__main__":
    sys.exit(main())
