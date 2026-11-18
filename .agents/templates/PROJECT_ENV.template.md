# PROJECT_ENV — 环境事实

> 只写 agent 首轮需要、仓库里看不出来的事实；安装后逐条填实，未验证的写"未知"。

## 路径与命令
- 仓库根：<绝对路径>
- 自检：`python .agents/scripts/check_governance.py --strict`
- 钩子：`core.hooksPath=.githooks`

## Git 与远端
- 提交只经 git-vault `vault_commit_push`；推送走三端同步（按实际远端填写）
- 裸 `git commit` / `git push` 会被 cc-safety-net 拒绝

## 写权限与已知坑
- <本机特有的写入限制、路径怪癖>

## 边界
- 架构结论见项目文档；执行状态见执行台账
