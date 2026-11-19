---
name: governance-init
description: 用本仓治理栈初始化一个工作区（AGENTS.md、rules 01-14、checker、审批收据门禁、评测状态），装完自动验证 hooks 与 checker 是否真正生效。触发词：/governance-init、初始化治理、部署治理框架、给工作区装 agent 规则。若目标工作区已有旧版 init-agent 产物，以本仓为准并报告差异。
---

# governance-init

## 何时用

用户要求给一个新工作区（或存量项目）部署本仓治理框架时。纯阅读或单任务不需要。

## 前置事实（先说清，别假装）

- 本技能只复制**仓库内**的部分：规则、checker、收据门禁、hooks、评测状态、AGENTS.md。
- 以下属于**机器级依赖**，脚本不会安装，缺失时 verify 只报 WARN：
  - `~/.cc-safety-net/rules/rule.json`（裸 git 拦截）
  - `<path>/...`（提交与凭据通道，端口 8765）
  - Python 3（checker 与脚本依赖）

## 两种装法

- **覆盖式**（默认）：保留目标仓已有同名文件，需要更新时加 `--force`。
- **清装式**（`--clean`）：先把 `AGENTS.md`/`.agents/`/`.githooks/` 备份到 `.agents.bak-<ts>/` 再移除，然后全新部署；业务文件不动。破坏性操作，必须先 dry-run 给用户看清单。

部署来源只认本仓（clone/pull），不要再用 `<path>/...` 旧模板。部署手册见 `docs/deploy.md`。

## 步骤

0. **探测写入口（必做）**：`curl -s http://127.0.0.1:8765/api/status`（或 `python scripts/fetch_vault.py --check`）。在线则继续；离线时明确告知两条路——运行 `/init-gitvault` 安装（推荐），或 `--git-mode local --reason "<原因>"` 备案。bootstrap 会把结果写入目标仓 `.agents/git-mode.json`；不得静默选择裸 git。

1. 先 dry-run，把将创建/跳过/覆盖的文件列给用户：
   ```bash
   python .agents/scripts/bootstrap_workspace.py --target <目标目录>
   ```
2. 用户确认后再写入；已有文件默认保留，需覆盖才加 `--force`：
   ```bash
   python .agents/scripts/bootstrap_workspace.py --target <目标目录> --apply
   ```
3. **初始化结束后必须询问用户项目类型**（代码 / 文档 / 调研 / 实验 / 其他），不得默认；得到回答后再填 `docs/governance-map.md`（删掉 `STATUS: PLACEHOLDER` 与 `PROJECT_TYPE: 未指定` 两行）和 `docs/environment-todo.md`。
4. 脚本会自动跑 `verify_governance.py` 与目标仓的 `checker --strict`。把失败项原样贴给用户，不要改写成"基本完成"。
4. 目标目录不是 git 仓库时，提示用户先 `git init`，否则 `core.hooksPath` 无法设置。

## 判定标准

- `verify` 的 FAIL 必须先清零；WARN 属于机器级依赖，明确告诉用户缺什么。
- 目标仓 checker 不是 exit 0 时，不得声称初始化完成。

## 与旧技能的关系

全局 `init-agent` / `init` 是旧模板（缺 rule 14、无 frontmatter、无 hooks、checker 停留在 P0 前）。本技能产出若与旧产物冲突，以本仓为准，并在报告里列出差异。