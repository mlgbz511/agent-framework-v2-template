# agent-framework-v2-template

> 本仓是 agent-framework-v2 治理框架的公开模板快照；事实源在私有仓，私有历史不进入公开仓。

## 用途

把一个工作区初始化为受治理的 agent workspace：AGENTS.md 指令链、rules 01-14、checker 静态门禁、审批收据、提交钩子、governance-init 技能。

## 快速开始

    git clone http<path>/...
    python agent-framework-v2-template/scripts/bootstrap_workspace.py --target <你的目录>          # dry-run
    python agent-framework-v2-template/scripts/bootstrap_workspace.py --target <你的目录> --apply
    python agent-framework-v2-template/.agents/scripts/verify_governance.py --target <你的目录> --require-external --print-remedies

## 包含

AGENTS.md、rules 01-14、checker / approval_gate / verify、.githooks、task-modes 与 governance-init 技能、docs/deploy.md、docs/prereqs.md。

## 不包含

真实环境事实、审计证据、审批收据、私有仓历史、项目文档与图片。

## 自检

    python .agents/scripts/check_governance.py --strict
