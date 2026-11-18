# agent-framework-v2-template

[![version](https://img.shields.io/github/v/tag/mlgbz511/agent-framework-v2-template?label=version)](https://github.com/mlgbz511/agent-framework-v2-template/tags)

> 本仓是 agent-framework-v2 治理框架的公开模板快照；事实源在私有仓，私有历史不进入公开仓。

## 用途

把一个工作区初始化为受治理的 agent workspace：AGENTS.md 指令链、rules 01-14、checker 静态门禁、审批收据、提交钩子、governance-init 技能。

## 三种获取方式

| 方式 | 适合 | 命令 |
|---|---|---|
| 技能包（推荐） | 只想装全局技能 | 见下方"仅安装技能" |
| 克隆本仓 | 要在本仓里跑/改脚本 | `git clone` 后 bootstrap |
| 直接 bootstrap | 已有一份副本 | `python scripts/bootstrap_workspace.py --target . --apply` |

### 仅安装技能（任意 agent 主机）

```bash
curl -LO https://raw.githubusercontent.com/mlgbz511/agent-framework-v2-template/main/governance-init-skills.tar.gz
tar xzf governance-init-skills-*.tar.gz -C ~/.dsh/skills/
# Gemini / Antigravity 主机改为 -C ~/.gemini/config/skills/
```

包内含 `governance-init`（带 assets payload）与 `init`/`init-agent` 兼容别名。

## 快速开始

    git clone https://github.com/mlgbz511/agent-framework-v2-template.git
    python agent-framework-v2-template/scripts/bootstrap_workspace.py --target <你的目录>          # dry-run
    python agent-framework-v2-template/scripts/bootstrap_workspace.py --target <你的目录> --apply
    python agent-framework-v2-template/.agents/scripts/verify_governance.py --target <你的目录> --require-external --print-remedies

## 包含

AGENTS.md、rules 01-14、checker / approval_gate / verify、.githooks、task-modes 与 governance-init 技能、docs/deploy.md、docs/prereqs.md。

## 不包含

真实环境事实、审计证据、审批收据、私有仓历史、项目文档与图片。

## 自检

    python .agents/scripts/check_governance.py --strict
