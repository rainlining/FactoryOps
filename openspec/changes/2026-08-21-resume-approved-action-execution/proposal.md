# Change 提案：批准后执行业务动作并恢复 Run

- `change_id`: `2026-08-21-resume-approved-action-execution`
- `status`: `applying`
- `learning_level`: `deep`
- `depends_on`: `2026-08-21-pause-run-for-human-approval`
- `feature_branch`: `codex/resume-approved-action-execution`

本 Change 把 Java 返回的 terminal APPROVED Human Approval 保存为 Agent 事实，调用 Java 版本化幂等执行 API，并在执行回执验证后把来源 Run 从 `WAITING_FOR_APPROVAL` 恢复为 `RUNNING`。它闭合“等待人工 → 已批准 → 真实 Batch hold → workflow resume”链路，并对跨数据库崩溃窗口提供可重放恢复。

非目标：不完成 Coordinator Execution/Run，不处理 REJECTED/EXPIRED 的终态策略，不执行 STOP_LINE/REJECT_ITEM，不新增 Kafka/UI，不修改 `dataset/`。

学习等级 `deep`：首次跨 Java Business DB 与 Agent DB 实现幂等 saga 和 crash-window recovery。Owner Review/Learning 延后至 demo milestone。本 Change 是 demo 路线第 7/10 个，完成后最多剩 3 个。
