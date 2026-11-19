#!/usr/bin/env python3
"""Bootstrap the governance stack into a target workspace.

Default is dry-run; pass --apply to write. Existing files are kept unless --force.
"""
import argparse
import filecmp
import json
import os
import platform
import re
import shutil
import subprocess
import sys
import time

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
FILES = [
    "AGENTS.md",
    ".agents/mcp_config.example.json",
    ".agents/approvals/README.md",
    ".agents/templates/task_plan_template.md",
    ".agents/scripts/skill_curator.py",
    ".agents/scripts/gitingest_tool.py",
    "docs/audits/p1-eval-plan.md",
    "docs/design/claude-design-system.md",
    "scripts/publish_diagram.py",
    "scripts/bootstrap_workspace.py",
    ".agents/templates/git-mode.json",
]
STUBS = {
    "docs/governance-map.md": "# 架构与断点\n\nSTATUS: PLACEHOLDER\nPROJECT_TYPE: 未指定（初始化后必须询问用户，不得默认）\n\n> 占位文件：本工作区的层结构、优先级与已知断点待填。安装后按实际项目补全。\n\n## 指令链预算\n- 每链 65536，两链合计 131072（DSH 注入预算）。\n",
    "docs/environment-todo.md": "# 执行台账\n\nSTATUS: PLACEHOLDER\n\n> 占位文件：本工作区环境与治理任务的执行状态待填；首轮事实写到 PROJECT_ENV.md。\n",
    "docs/audits/evals/status.md": "last_run: 2026-01-01\nE1: 未执行\nE2: 未执行\nE3: 未执行\nrecorded_by: template\n",
}
DIRS = [".agents/rules", ".githooks", "docs/audits/evals"]
SCRIPTS = [
    ".agents/scripts/check_governance.py",
    ".agents/scripts/approval_gate.py",
    ".agents/scripts/requirements.txt",
    ".agents/scripts/verify_governance.py",
]
SKILLS_DEFAULT = [".agents/skills/task-modes"]
REF_RE = re.compile(r"`((?:\.agents|docs|scripts|assets)/[^`\s]+)`")
SKIP_REF = (".agents/", ".agents/skills/", "docs/", "assets/")
OPTIONAL_REF = (
    "docs/PROGRESS.md",
    "docs/DECISIONS.md",
    "docs/PROJECT_ENV.md",
    "docs/_pending/",
)
GOV_PATHS = ("AGENTS.md", ".agents", ".githooks")


def referenced_paths():
    texts = []
    agents = relsrc("AGENTS.md")
    if os.path.exists(agents):
        with open(agents, "r", encoding="utf-8", errors="replace") as fh:
            texts.append(fh.read())
    rules_dir = relsrc(".agents/rules")
    for name in sorted(os.listdir(rules_dir)) if os.path.isdir(rules_dir) else []:
        if name.endswith(".md"):
            with open(os.path.join(rules_dir, name), "r", encoding="utf-8", errors="replace") as fh:
                texts.append(fh.read())
    refs = set()
    for text in texts:
        for match in REF_RE.finditer(text):
            refs.add(match.group(1).rstrip(".,;:"))
    return sorted(refs)


def closure():
    copy, stubs, skipped, missing = [], [], [], []
    for rel in referenced_paths():
        if rel.endswith("/") or rel in SKIP_REF or rel in OPTIONAL_REF or rel.endswith(".local.md"):
            skipped.append(rel)
        elif "<" in rel or ">" in rel:  # 文档里的模板占位（如 <项目名>）不是真实路径
            skipped.append(rel)
            skipped.append(rel)
        elif rel in STUBS:
            stubs.append(rel)
        elif os.path.exists(relsrc(rel)):
            copy.append(rel)
        else:
            missing.append(rel)
    return copy, stubs, skipped, missing


def backup_root(target, in_repo):
    if in_repo:
        return target
    return os.path.join(os.path.dirname(target), ".gov-backups")


def clean_backup(target, in_repo):
    base = backup_root(target, in_repo)
    stamp = time.strftime("%Y%m%d-%H%M%S")
    name = (".agents.bak-%s" % stamp) if in_repo else ("%s-%s" % (os.path.basename(target), stamp))
    backup = os.path.join(base, name)
    moved = []
    os.makedirs(backup, exist_ok=True)
    for rel in GOV_PATHS:
        src = os.path.join(target, rel)
        if os.path.exists(src):
            shutil.move(src, os.path.join(backup, rel.replace("/", "_")))
            moved.append(rel)
    return backup, moved


def purge_backups(target, days, apply):
    base = os.path.join(os.path.dirname(target), ".gov-backups")
    if not os.path.isdir(base):
        print("PURGE           %s 不存在，无备份可清" % base)
        return
    cutoff = time.time() - days * 86400
    for name in sorted(os.listdir(base)):
        path = os.path.join(base, name)
        if not os.path.isdir(path) or os.path.getmtime(path) >= cutoff:
            continue
        print("%s%s" % ("PURGE          " if apply else "PURGE-PLAN     ", path))
        if apply:
            shutil.rmtree(path, ignore_errors=True)


def git_out(target, *cmd):
    res = subprocess.run(["git"] + list(cmd), cwd=target, capture_output=True, text=True,
                         encoding="utf-8", errors="replace")
    return res.stdout.strip() if res.returncode == 0 else ""


def sanitize_remote(url):
    return re.sub(r"//[^/@\s]+@", "//", url)


def write_env(target):
    remote = sanitize_remote(git_out(target, "remote", "get-url", "origin")) if os.path.isdir(os.path.join(target, ".git")) else ""
    branch = git_out(target, "rev-parse", "--abbrev-ref", "HEAD") if remote else ""
    hooks = git_out(target, "config", "--get", "core.hooksPath") if remote else ""
    content = """# PROJECT_ENV — 环境事实

> 自动探测于 {date}；结果只代表当时环境，换机或改配置后重跑 bootstrap 更新。

## 自动探测
- 仓库根：{root}
- Python：{python}
- 系统：{platform}
- git 远端：{remote}
- 当前分支：{branch}
- core.hooksPath：{hooks}

## 人工确认（待填）
- 端口与本地服务：未知（待填）
- 服务端点与代理：未知（待填）
- 写入限制/ACL 怪癖：未知（待填）
- 凭据边界：未知（待填）

## 边界
- 架构结论以 docs/governance-map.md 为准；执行状态以 docs/environment-todo.md 为准。
""".format(date=time.strftime("%Y-%m-%d"), root=target, python=platform.python_version(),
           platform=platform.platform(), remote=remote or "未配置",
           branch=branch or "未提交/未知", hooks=hooks or "未设置")
    path = os.path.join(target, "PROJECT_ENV.md")
    if os.path.exists(path):
        return False
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(content)
    return True


def relsrc(path):
    return os.path.join(ROOT, path)


def plan_entry(target, rel, force):
    src = relsrc(rel)
    dst = os.path.join(target, rel)
    if not os.path.exists(src):
        return ("MISSING-SRC", rel)
    if os.path.isdir(src):
        if not os.path.exists(dst):
            return ("CREATE-DIR", rel)
        return ("MERGE-DIR", rel)
    if not os.path.exists(dst):
        return ("CREATE", rel)
    if filecmp.cmp(src, dst, shallow=False):
        return ("SAME", rel)
    return ("OVERWRITE" if force else "KEEP-EXISTING", rel)


def collect(args):
    items = list(FILES) + DIRS + SCRIPTS + closure()[0]
    if args.skills == "all":
        skills = [".agents/skills/" + d for d in sorted(os.listdir(relsrc(".agents/skills")))
                  if os.path.isdir(relsrc(".agents/skills/" + d))]
    else:
        skills = SKILLS_DEFAULT
    return items + skills


def copy_tree(src, dst, force):
    created = 0
    for name in os.listdir(src):
        s = os.path.join(src, name)
        d = os.path.join(dst, name)
        if os.path.isdir(s):
            os.makedirs(d, exist_ok=True)
            created += copy_tree(s, d, force)
        else:
            if os.path.exists(d) and not force:
                continue
            shutil.copy2(s, d)
            created += 1
    return created


def apply(target, rel, force):
    src = relsrc(rel)
    if not os.path.exists(src):
        print("SKIP-MISSING-SRC %s" % rel)
        return 0
    dst = os.path.join(target, rel)
    if os.path.isdir(src):
        if rel == ".agents/rules" and os.path.isdir(dst):
            created = 0
            for name in os.listdir(src):
                d = os.path.join(dst, name)
                if os.path.exists(d) and not force:
                    continue
                shutil.copy2(os.path.join(src, name), d)
                created += 1
            return created
        os.makedirs(dst, exist_ok=True)
        return copy_tree(src, dst, force)
    os.makedirs(os.path.dirname(dst), exist_ok=True)
    if os.path.exists(dst) and not force:
        return 0
    shutil.copy2(src, dst)
    return 1



def vault_online(timeout=2.0):
    import urllib.request
    try:
        url = os.environ.get("GIT_VAULT_API", "http://127.0.0.1:8765") + "/api/status"
        with urllib.request.urlopen(url, timeout=timeout) as resp:
            return 200 <= getattr(resp, "status", 0) < 300
    except Exception:
        return False


def resolve_git_mode(args, target):
    """返回 (mode, reason) 或 (None, 错误信息)。"""
    online = vault_online()
    mode = args.git_mode
    reason = args.reason or ""
    if mode == "auto":
        if online:
            return "vault", "vault 在线（自动探测）"
        return None, ("vault 未在线。两条路：\n"
                      "  1) 运行 /init-gitvault 安装（推荐）\n"
                      "  2) 不安装并备案：--git-mode local --reason \"<原因>\"（30 天有效）")
    if mode == "vault":
        if not online:
            return None, "指定 --git-mode vault，但 /api/status 不可达"
        return "vault", reason or "vault 在线"
    if mode == "local":
        if online:
            return None, "vault 在线时禁止降级为 local（防绕过门禁）；改用 --git-mode vault"
        if not reason:
            return None, "--git-mode local 必须同时给 --reason"
        return "registered-exception", reason
    return None, "未知 --git-mode: %s" % mode


def write_git_mode(target, mode, reason):
    path = os.path.join(target, ".agents", "git-mode.json")
    os.makedirs(os.path.dirname(path), exist_ok=True)
    today = time.strftime("%Y-%m-%d")
    expires = None
    receipt = None
    if mode == "registered-exception":
        expires = time.strftime("%Y-%m-%d", time.localtime(time.time() + 30 * 86400))
        receipt = ".agents/approvals/%s-no-vault-exception.md" % today
        rpath = os.path.join(target, receipt)
        with open(rpath, "w", encoding="utf-8", newline="\n") as fh:
            fh.write("category: gate-change\n"
                     "targets: git-write-path\n"
                     "impact: 本工作区无 git-vault 写入口，按规则 14 §1.1 允许本机 git\n"
                     "rollback: init --git-mode vault（vault 在线时）或删除 git-mode.json\n"
                     "approver: user\n"
                     "date: %s\nexpires_at: %s\n" % (today, expires))
    data = {
        "mode": mode,
        "reason": reason,
        "decided_by": "user",
        "decided_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "expires_at": expires,
        "receipt": receipt,
    }
    with open(path, "w", encoding="utf-8", newline="\n") as fh:
        json.dump(data, fh, ensure_ascii=False, indent=2)
        fh.write("\n")
    return path


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--target", required=True)
    ap.add_argument("--source", default=None,
                    help="治理源仓路径（默认用本脚本所在仓）；用于在目标仓内部执行 init")
    ap.add_argument("--apply", action="store_true")
    ap.add_argument("--force", action="store_true")
    ap.add_argument("--skills", choices=("task-modes", "all"), default="task-modes",
                    help="task-modes 为最小集（AGENTS §2 依赖该技能）")
    ap.add_argument("--clean", action="store_true",
                    help="先备份并移除目标仓旧治理文件（AGENTS.md/.agents/.githooks）再部署")
    ap.add_argument("--backup-in-repo", action="store_true",
                    help="备份放入目标仓（默认放父目录 .gov-backups，避免被提交）")
    ap.add_argument("--purge-backups", type=int, metavar="DAYS",
                    help="清理父目录 .gov-backups 中超过 DAYS 天的备份；加 --apply 才真删")
    ap.add_argument("--git-mode", choices=("auto", "vault", "local"), default="auto",
                    help="auto=探测后自动选 vault；local=未装 vault 时显式备案（需 --reason）")
    ap.add_argument("--reason", default="", help="--git-mode local 的备案原因")
    args = ap.parse_args()

    global ROOT
    if args.source:
        ROOT = os.path.abspath(args.source)
        if not os.path.exists(os.path.join(ROOT, "AGENTS.md")):
            print("source 不像治理源仓（缺 AGENTS.md）：%s" % ROOT)
            return 2
    print("source=%s" % ROOT)

    target = os.path.abspath(args.target)
    if not os.path.isdir(target):
        print("target 不存在：%s" % target)
        return 2

    probe = os.path.join(target, ".bootstrap-probe")
    try:
        with open(probe, "w", encoding="utf-8") as fh:
            fh.write("probe")
        os.remove(probe)
    except OSError as exc:
        print("目标目录不可写，拒绝在半途失败：%s" % exc)
        return 2

    mode, mode_msg = resolve_git_mode(args, target)
    if mode is None:
        print("GIT-MODE       拒绝：%s" % mode_msg)
        return 3
    print("GIT-MODE       %s（%s）" % (mode, mode_msg))

    if args.purge_backups is not None:
        purge_backups(target, args.purge_backups, args.apply)

    copy_refs, stub_refs, skip_refs, missing_refs = closure()
    print("-- closure: copy=%d stub=%d skip=%d missing=%d"
          % (len(copy_refs), len(stub_refs), len(skip_refs), len(missing_refs)))
    for rel in stub_refs:
        print("CLOSURE-STUB   %s" % rel)
    for rel in missing_refs:
        print("CLOSURE-MISSING %s（本仓无此文件，请补或改引用）" % rel)
    if args.clean:
        print("CLEAN-PLAN    备份并移除：%s" % ", ".join(GOV_PATHS))

    results = [plan_entry(target, rel, args.force) for rel in collect(args)]
    for status, rel in results:
        print("%-14s %s" % (status, rel))
    counts = {}
    for status, _ in results:
        counts[status] = counts.get(status, 0) + 1
    print("-- summary: %s" % ", ".join("%s=%d" % kv for kv in sorted(counts.items())))

    if not args.apply:
        print("dry-run：加 --apply 才会写入（--force 覆盖已存在文件）")
        return 0

    if args.clean:
        backup, moved = clean_backup(target, args.backup_in_repo)
        print("CLEAN         备份=%s 移除=%s"
              % (os.path.basename(backup), ",".join(moved) if moved else "无既有治理文件"))

    written = 0
    for rel in collect(args):
        written += apply(target, rel, args.force)
    if write_env(target):
        written += 1
        print("CREATE         PROJECT_ENV.md（自动探测）")
    else:
        print("KEEP           PROJECT_ENV.md（已存在，不覆盖）")
    gmpath = write_git_mode(target, mode, mode_msg)
    print("GIT-MODE       写入 %s" % os.path.relpath(gmpath, target).replace(os.sep, "/"))

    for rel, text in STUBS.items():
        dst = os.path.join(target, rel)
        if os.path.exists(dst):
            continue
        os.makedirs(os.path.dirname(dst), exist_ok=True)
        with open(dst, "w", encoding="utf-8") as fh:
            fh.write(text)
        written += 1
        print("STUB           %s" % rel)

    if os.path.isdir(os.path.join(target, ".git")):
        res = subprocess.run(["git", "config", "core.hooksPath", ".githooks"],
                             cwd=target, capture_output=True, text=True)
        print("hooksPath     %s" % ("ok" if res.returncode == 0 else res.stderr.strip()[:80]))

    print("written=%d" % written)
    print("--- next steps（必须执行，不要默认项目类型）---")
    print("[ ] 询问用户：本工作区属于哪类项目（代码 / 文档 / 调研 / 实验 / 其他）？")
    print("[ ] 按用户回答补 docs/governance-map.md（删除 STATUS/PROJECT_TYPE 占位行）")
    print("[ ] 补 docs/environment-todo.md 与 PROJECT_ENV.md 的人工确认项")
    for name in ("verify_governance.py",):
        script = os.path.join(target, ".agents", "scripts", name)
        if os.path.exists(script):
            res = subprocess.run([sys.executable, "-B", script, "--target", target],
                                 capture_output=True, text=True, encoding="utf-8", errors="replace")
            print("--- verify ---")
            print((res.stdout or res.stderr).strip())
    checker = os.path.join(target, ".agents", "scripts", "check_governance.py")
    if os.path.exists(checker):
        res = subprocess.run([sys.executable, "-B", checker, "--strict"], cwd=target,
                             capture_output=True, text=True, encoding="utf-8", errors="replace")
        print("--- checker (target) ---")
        print(((res.stdout or "") + (res.stderr or "")).strip()[-600:])
        print("checker exit=%d" % res.returncode)
    return 0


if __name__ == "__main__":
    sys.exit(main())