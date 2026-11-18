# 环境前置依赖

> 只写机器级依赖：仓库装不了、也不该偷偷装。每条给检查命令与修复入口；实测日期 2026-11-19。

## 1. Python 3

- 检查：`python --version`
- 用途：checker、approval_gate、bootstrap、verify
- 缺失：安装 Python 3.11+ 并确保 `python` 在 PATH

## 2. cc-safety-net（裸 git 拦截）

- 检查：`ls ~/.cc-safety-net/rules/rule.json`
- 期望：存在用户策略，且包含 `global-deny`；否则 `git commit` / `git push` 不会被拦
- 修复：按 cc-safety-net 文档注册 `ops_bash` 为 command tool 并写入策略
- verify 显示：`缺 cc-safety-net 用户策略`

## 3. git-vault（提交与凭据通道）

- 检查：`curl -s http://127.0.0.1:8765/api/status`
- 期望：200 JSON
- 修复：启动 `<path>/...` 的 server；仓库需登记在 git-vault 工具仓的 config 目录（managed_repos.json，不在本仓）
- verify 显示：`git-vault 网关不可达`

## 4. DPAPI 凭据

- 检查：`cfg` 中的“凭据”页能读出 PAT；或 vault 自身状态接口
- 期望：三端 token 已加密存储
- 修复：通过 vault 的凭据登记流程写入；不要手工存明文
- 边界：DPAPI 按 Windows 用户加密，同用户进程可解密；强隔离需独立服务账户

## 5. 网络与代理

- 检查：`curl -sS --max-time 5 https://gitlab.com`
- 期望：可达；不稳时经 `http.proxy=http://127.0.0.1:11455`
- 注意：直连与代理都会抖动，推送前先 `git ls-remote`

## 6. 验证入口

```bash
.agents/scripts/verify_governance.py --target . --require-external --print-remedies
```

退出码非 0 表示必需项缺失；`--print-remedies` 会针对每个 WARN/FAIL 打印对应修复入口。
