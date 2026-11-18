# 治理栈部署手册（本仓为唯一源）

> 外部模板 `<path>/...` 已废弃：只作历史归档，不再作为部署来源。部署一律"克隆/拉取本仓 → bootstrap → verify"。

## 前置

| 依赖 | 必需 | 缺失表现 |
|---|---|---|
| Python 3 | 是 | bootstrap 无法运行 |
| git | 是 | 无法设置 hooksPath |
| cc-safety-net 用户策略 | 建议 | 裸 `git commit/push` 不被拦（verify 报 WARN） |
| git-vault 网关 | 建议 | 提交通道不可用（verify 报 WARN） |
| DPAPI 凭据 | 建议 | 认证需手工处理 |

## 覆盖式部署（保留目标仓业务文件）

```bash
git clone https://github.com/<owner>/agent-framework-v2.git .gov-src
python .gov-src/scripts/bootstrap_workspace.py --target <目标目录>            # dry-run
python .gov-src/scripts/bootstrap_workspace.py --target <目标目录> --apply
.agents/scripts/verify_governance.py --target <目标目录>
```

- 已存在的同名文件默认保留；需要更新治理文件时加 `--force`。
- 目标仓的 `PROJECT_ENV.md`、`docs/governance-map.md`、`docs/environment-todo.md` 若不存在会生成占位，verify 会持续提示"占位未填"。

## 在目标仓内部执行 init

目标仓里已有一份脚本副本（或脚本可从别处调用）时，用 `--source` 指向治理源仓：

```bash
python scripts/bootstrap_workspace.py --target . --source <治理源仓路径>          # dry-run
python scripts/bootstrap_workspace.py --target . --source <治理源仓路径> --apply
```

- 不带 `--source` 时，源仓默认取脚本所在位置；脚本就在目标仓里而目标仓还没有治理文件时，必须显式给 `--source`。
- 重复执行是幂等的：已一致的文件报 `SAME`，目录报 `MERGE-DIR`。

## 清装式部署（删旧治理文件后重装）

```bash
python bootstrap_workspace.py --target <目标目录> --clean            # dry-run，先看清单
python bootstrap_workspace.py --target <目标目录> --clean --apply
```

- 会先备份到 `.agents.bak-<时间戳>/`，再移除 `AGENTS.md`、`.agents/`、`.githooks/`；业务文件不动。
- 备份目录不自动删除，确认无误后手工清理。

## 引用闭包

bootstrap 从 `AGENTS.md` 与 `rules/*.md` 提取反引号路径，按四类处理：

| 类别 | 处理 |
|---|---|
| 本仓存在且非仓专属 | 复制 |
| 仓专属（governance-map / environment-todo） | 生成 `STATUS: PLACEHOLDER` 占位 |
| 个人/本地（`.local.md`、PROGRESS、DECISIONS、`_pending/`、`<项目名>` 模板） | 跳过 |
| 引用存在但本仓没有 | 报 `CLOSURE-MISSING`，需修引用 |

## 回滚

1. 覆盖式：`git checkout -- AGENTS.md .agents .githooks`。
2. 清装式：把 `.agents.bak-<时间戳>/` 里的目录移回原位。
3. 两者的治理文件变更都可用 `git revert` 回退。

## 验证清单

```bash
python .agents/scripts/check_governance.py --strict      # exit 0
.agents/scripts/verify_governance.py --target .          # fail=0
# 收据门禁（在目标仓里）
echo "<!-- probe -->" >> .agents/rules/06-domain-whitelist.md
git add -A && sh .githooks/pre-commit; echo exit=$?      # 期望 1
```
