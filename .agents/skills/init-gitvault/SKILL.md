---
name: init-gitvault
description: 在缺少 git-vault 的主机上安装并启动网关（Windows/DPAPI）；触发词 /init-gitvault、安装 git-vault、部署 vscode vault 网关、补写入口。安装前必须探测并征得用户同意。
---

# init-gitvault

## 何时使用

- 目标工作区 `init` 后 `GIT-MODE` 提示 vault 离线，用户选择"安装"；
- 新主机需要唯一 Git 写入口与凭据代理。

## 步骤

1. **探测**：`python <skill>/scripts/fetch_vault.py --check`。已在线则直接结束，输出 `/api/status` 证据。
2. **平台检查**：仅 Windows（DPAPI）。非 Windows 直接说明不支持，建议备案（规则 14 §1.1），不得降级假装成功。
3. **征得同意**：告知将下载 `vault.pyz`、写入 `~/.git-vault/`、启动后台进程；未同意不得继续。
4. **下载并校验**：`python fetch_vault.py`。sha256 不匹配必须中止并删除本次下载。
5. **启动并复检**：脚本轮询 `/api/status` 最多 30 秒；超时即失败，杀进程并清理。
6. **接入工作区**：回到目标仓执行 `init --git-mode vault`（或 `bootstrap --git-mode vault`），确认 `checker` 通过。
7. **失败处置**：保留日志，删除本次新增文件，报告失败原因；工作区保持 `registered-exception` 或未初始化状态，不得静默放行。

## 约束

- 不打印、不生成任何 token；凭据仍由用户在平台生成后写入 vault。
- 不跳过 sha256 校验；不使用 `curl | sh` 之类不可审的形式。
- 非 Windows 不支持；Linux/macOS 走备案或等待移植版。
- 安装失败不得把 `git-mode.json` 改成 vault。
