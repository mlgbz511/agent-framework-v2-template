#!/usr/bin/env python3
"""Fetch, verify and start git-vault (vault.pyz) on a host without it.

Usage:
  python fetch_vault.py --check            # 只探测，不下载
  python fetch_vault.py                    # 下载+校验+启动（默认目录 ~/.git-vault）
  python fetch_vault.py --url <base>       # 自定义来源（目录 URL，含 vault.pyz/SHA256SUMS）
  python fetch_vault.py --stop             # 停止本次启动的进程（记录 pid 文件）
"""
import argparse
import hashlib
import json
import os
import platform
import shutil
import subprocess
import sys
import time
import urllib.request

BASE = os.environ.get("GIT_VAULT_RELEASE_BASE",
                      "https://raw.githubusercontent.com/mlgbz511/git-vault/main")
API = os.environ.get("GIT_VAULT_API", "http://127.0.0.1:8765")
ARTIFACTS = ("vault.pyz", "SHA256SUMS")
EXAMPLES = ("vault.example.json", "managed_repos.example.json",
            "git_profiles.example.json", "network_routes.example.json")


def online(timeout=2.0):
    try:
        with urllib.request.urlopen(API + "/api/status", timeout=timeout) as r:
            return 200 <= getattr(r, "status", 0) < 300
    except Exception:
        return False


def fetch(url, dst):
    with urllib.request.urlopen(url, timeout=60) as r, open(dst, "wb") as fh:
        shutil.copyfileobj(r, fh)


def verify(path, sums_path):
    want = None
    with open(sums_path, "r", encoding="utf-8") as fh:
        for line in fh:
            parts = line.split()
            if len(parts) == 2 and parts[1].lstrip("*") == os.path.basename(path):
                want = parts[0]
                break
    if not want:
        return False, "SHA256SUMS 中没有 %s" % os.path.basename(path)
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(65536), b""):
            h.update(chunk)
    return (h.hexdigest() == want), ("sha256 不符：期望 %s 实际 %s" % (want, h.hexdigest()))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true")
    ap.add_argument("--url", default=BASE)
    ap.add_argument("--dir", default=os.path.expanduser("~/.git-vault"))
    ap.add_argument("--timeout", type=int, default=30)
    ap.add_argument("--stop", action="store_true")
    ap.add_argument("--force", action="store_true")
    args = ap.parse_args()

    if args.stop:
        pid_file = os.path.join(args.dir, "vault.pid")
        if os.path.exists(pid_file):
            pid = int(open(pid_file).read().strip() or 0)
            if pid:
                subprocess.run(["taskkill", "/PID", str(pid), "/F"], capture_output=True)
            os.remove(pid_file)
            print("stopped pid=%s" % pid)
        return 0

    if online() and not args.force:
        print("vault 已在线：%s" % API)
        return 0
    if args.check:
        print("vault 离线：%s" % API)
        return 1

    if platform.system() != "Windows":
        print("暂不支持 %s：DPAPI 仅 Windows 可用；请按规则 14 §1.1 备案" % platform.system())
        return 3

    os.makedirs(args.dir, exist_ok=True)
    cfg = os.path.join(args.dir, "config")
    os.makedirs(cfg, exist_ok=True)

    fetched = []
    try:
        for name in ARTIFACTS:
            dst = os.path.join(args.dir, name)
            fetch(args.url.rstrip("/") + "/" + name, dst)
            fetched.append(dst)
        ok, msg = verify(os.path.join(args.dir, "vault.pyz"), os.path.join(args.dir, "SHA256SUMS"))
        if not ok:
            print("校验失败：%s" % msg)
            return 4
        print("校验通过：vault.pyz sha256 匹配")
        for name in EXAMPLES:
            dst = os.path.join(cfg, name)
            if os.path.exists(dst):
                continue
            try:
                fetch(args.url.rstrip("/") + "/config/" + name, dst)
                fetched.append(dst)
            except Exception:
                pass
        pyz = os.path.join(args.dir, "vault.pyz")
        proc = subprocess.Popen([sys.executable, pyz], cwd=args.dir,
                                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                                creationflags=getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0))
        with open(os.path.join(args.dir, "vault.pid"), "w") as fh:
            fh.write(str(proc.pid))
        deadline = time.time() + args.timeout
        while time.time() < deadline:
            if online():
                print("vault 已启动：%s pid=%s" % (API, proc.pid))
                return 0
            time.sleep(1.5)
        print("启动超时（%ss）：/api/status 不可达" % args.timeout)
        proc.terminate()
        return 5
    except Exception as exc:
        print("失败：%s" % exc)
        for path in fetched:
            try:
                os.remove(path)
            except OSError:
                pass
        return 5


if __name__ == "__main__":
    sys.exit(main())
