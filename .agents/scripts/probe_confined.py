#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""沙箱限制探针：在指定目录试建并删除子项，输出原始证据。

用途：交接"某目录能否写入"的结论时，要求对方贴出本脚本原始输出，
避免把不同执行环境（IDE 终端 vs DSH 沙箱）当作同一环境验证。

用法：python .agents/scripts/probe_confined.py [目录 ...]
默认探测仓库根、.tmp、assets、docs、scripts、.agents。
退出码 0 = 探针已执行（不代表全部可写）；2 = 没有可测目录。
"""
import os
import sys

DEFAULT = [".", ".tmp", "assets", "docs", "scripts", ".agents"]


def probe(d):
    if not os.path.isdir(d):
        return "MISSING"
    path = os.path.join(d, ".probe_%d.tmp" % os.getpid())
    try:
        with open(path, "w", encoding="utf-8") as fh:
            fh.write("probe\n")
    except OSError as err:
        return "CREATE_DENY %s" % err.strerror
    try:
        os.remove(path)
    except OSError as err:
        return "DELETE_DENY %s" % err.strerror
    return "WRITABLE"


def main():
    dirs = sys.argv[1:] or DEFAULT
    rows = [(d, probe(d)) for d in dirs]
    for d, verdict in rows:
        print("%-12s %s" % (d, verdict))
    print("SUMMARY writable=%d denied=%d" % (
        sum(1 for _, v in rows if v == "WRITABLE"),
        sum(1 for _, v in rows if v != "WRITABLE")))
    return 0 if rows else 2


if __name__ == "__main__":
    sys.exit(main())
