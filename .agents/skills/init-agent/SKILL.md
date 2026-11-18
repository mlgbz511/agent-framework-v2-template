---
name: init-agent
description: 兼容别名：/init-agent 或说“初始化项目/初始化工作区”时，立即按 governance-init 技能执行（同一套 payload 与门禁）。
---

# init-agent（兼容别名）

本技能只做转发，不维护独立模板。

## 执行

1. 读取并遵循 `~/.dsh/skills/governance-init/SKILL.md`（或 `~/.gemini/config/skills/governance-init/SKILL.md`）中的完整步骤；
2. 使用 governance-init 技能自带的 assets/scripts/bootstrap_workspace.py（相对该技能目录），**不要**使用任何旧版 init-agent 脚本；
3. 装完必须跑 checker 与 verify，并询问项目类型后再填占位文档。

## 禁止

- 不得自行生成 rules 01–13 旧模板；
- 不得跳过 checker/verify 直接宣布完成。