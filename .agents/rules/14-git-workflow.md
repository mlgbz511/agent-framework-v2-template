---
scope: Git 写入口、分支、提交、推送与凭据
trigger: 任何 git 写操作、推送、分支合并、凭据使用
enforcement: hook
version: 1
---
# 14 — Git 工作流与写入口

## 适用范围
适用于任何 Git 仓库的写操作（提交、推送、分支、合并、标签、回退）。只读操作不受本规则限制。软件任务额外遵守规则 01、02；授权卡片使用规则 05。

## 1. 唯一写入口

- 提交、推送、分支、合并、标签、回退**只经 git-vault MCP 工具**：vault_commit_push、vault_git_status、vault_git_branch、vault_git_merge。
- 只读 git（status、diff、log、show、blame）可直接使用，不经网关。
- 无 git-vault 的环境不自动降级：先探测 `/api/status`。离线时只有两条路——运行 `/init-gitvault` 安装，或按 §1.1 显式备案；不得静默改用裸 git。
- 裸写由 cc-safety-net rulebook 拦截；拦截失效也要按本规则执行，不得把"没拦住"当作许可。

### 1.1 备案例外（唯一合法降级）

仅当以下全部成立时，本机 git 写操作才合法：

1. `.agents/git-mode.json` 的 `mode` 为 `registered-exception`；
2. `receipt` 指向的收据存在、`category: gate-change`、含 `approver: user`；
3. `expires_at` 未过期（默认 30 天）；
4. 探测到 git-vault 不在线。

任一条不成立即回到 §1：禁止裸写。checker 的 `GIT_MODE` 检查负责执行本例外，vault 在线时备案态直接 BLOCK。备案续期须重新取得用户批准并更新 `expires_at`。

## 2. 分支模型

- main 为唯一长期分支；单人仓库允许在 main 上线性提交，多人仓库必须走特性分支。
- 特性分支命名：feat/<slug>、fix/<slug>、docs/<slug>、chore/<slug>，slug 用 kebab-case。
- 合并只允许快进（ff）或 squash；多方并发时先 rebase 本地未推送提交，再快进合并。
- 禁止改写已推送的历史（rebase、amend、filter-branch 作用于公共分支）。

## 3. 提交信息

- 标题格式：type(scope): subject，type 取自 feat、fix、docs、chore、refactor、test、governance、release；scope 可选，小写 kebab-case。
- subject 4 字符以上、整行不超过 100 字符；正文说明动机、影响与验证方式。
- 由 .githooks/commit-msg 强制；不合规提交由网关拒绝，不得用 --no-verify 规避。
- 网关自动附加的 Co-authored-by 行不参与校验。

## 4. 禁区

- git push --force / --force-with-lease 指向共享分支。
- filter-branch、git replace、直接编辑 .git 内部文件。
- 未获批准就执行 reset --hard 或丢弃未提交改动。
- 跨仓库批量推送、批量历史重写。
- 把凭据、密钥、内网地址写入提交内容或提交信息。

## 5. 发布与标签

- 标签格式 vYYYY.MM.DD-<slug>，使用 annotated tag。
- 只在 main 上、checker 退出码 0、三端推送完成后打标签。
- 发布前必须跑 vault_audit_compliance 且无 BLOCK。

## 6. 大文件与敏感物

- 仓库根不得存在单文件 >50MB（Gitee 限额）或明文凭据。
- 必须先把这类文件移出到 _quarantine（见 docs/governance-map.md §7），再提交。
- 合规守卫扫整棵工作树且无视 .gitignore，任何时候只要文件还在仓库根内就会阻断提交。

## 7. 授权分层

- 计划批准不等于获准提交，提交批准不等于获准推送（规则 02 §2）。
- 推送前必须按规则 05 提交卡片，说明仓库、目标平台、提交范围、回滚方式。
- Panic 只读锁开启时禁止一切写操作；只读与 diff 仍可用。

## 8. 审计与失败处理

- 所有写操作经网关记录在 mcp_audit.log；失败必须报告原始错误，不得改写为"已提交"。
- 提交被 checker 或 commit-msg 阻断时，修复后重试；不得删除断言、跳过检查或关闭钩子（底线定义见规则 02 §4）。
## 9. 凭据唯一来源

- Git 认证与外部 API 只经 git-vault：vault_commit_push / vault_git_*（token 走 DPAPI 存储与管道）与 vault_proxy_api（外部服务）。
- 不得读取、复制、回显、转存 PAT、SSH 私钥、.env、api-key 文件；不得把凭据写入命令参数、环境变量、URL、日志或提交内容。
- 禁止 GIT_ASKPASS、http.extraheader、指向非 vault helper 的 credential.helper，禁止 URL 内嵌 user:token@。
- 不得用路径变体规避密钥路径检测（如 /c/Users/... 或变量拼接）；检测放行不等于许可。
- 缺凭据时报告缺口（平台、key 类型、用途），请用户在 git-vault 面板补录；不得自行寻找替代密钥。
- 受控例外：B 方案（按仓 deploy key）必须在 docs/environment-todo.md 的 T21 登记，并说明 A 路线为何不可用。
- 每次凭据操作在交付说明中写明平台、key 类型、是否经 vault。
- 边界：DPAPI 由当前 Windows 用户加密，同用户进程可解密；本规则约束行为与默认路径，不宣称物理隔离（强隔离需独立服务账户）。