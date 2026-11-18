# 审批收据（Approval Receipts）

提交前门禁 `approval_gate.py` 会在下列情况要求一份**同一次提交里**的收据：

| 类别 | 触发条件 |
|---|---|
| `deletion` | 删除已跟踪文件 ≥3 个，或删除受保护路径下的文件 |
| `protected-change` | 修改 `AGENTS.md`、`.agents/rules/`、`.agents/scripts/check_governance.py`、`.agents/scripts/approval_gate.py`、`.githooks/` |
| `dependency` | 修改 `.agents/scripts/requirements.txt`、`package.json`、`package-lock.json`、`pnpm-lock.yaml`、`pyproject.toml`、`poetry.lock` |
| `gate-change` | 修改 hooks / checker / approval_gate 自身（与 protected-change 重叠时按更严者） |

## 文件格式

文件名：`YYYY-MM-DD-<slug>.md`，放在本目录。必填字段（每行 `key: value`）：

```
category: deletion
targets: docs/old-a.md, docs/old-b.md, docs/old-c.md
impact: 删除三份过期审计稿，无外部依赖
rollback: git checkout HEAD -- <paths>
approver: <用户名或工单号>
date: 2026-11-19
```

- `category` 取上表四值之一；一次提交涉及多类时，各写一份。
- `approver` 必须是人或工单号，不能是 agent 自述。
- 收据只证明"有人批准过"，不证明判断质量；抽查靠审计记录。
