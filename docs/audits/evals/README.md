# 行为评测记录（Evidence）

本目录存放人工执行的行为评测记录，供 `checker` 的 `EVAL_STATUS` 校验。

## 记录格式

文件 `YYYY-MM-DD-<id>.md`，按 `docs/audits/p1-eval-plan.md` 执行并记录：会话 id、提示词、命令原文、退出码、结论。

## 聚合状态

`status.md` 是本目录的汇总，字段固定：

```
last_run: YYYY-MM-DD
E1: 确定性拦截 | 指令层自律 | 未通过 | 未执行
E2: ...
E3: ...
recorded_by: <人>
```

格式由 checker 校验；新鲜度只做 WARN（超过 180 天提醒）。
