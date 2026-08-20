# Change 提案：为人工审批暂停 Agent Run

- `change_id`: `2026-08-21-pause-run-for-human-approval`
- `status`: `applying`
- `learning_level`: `deep`
- `depends_on`: `2026-08-20-execute-approved-batch-hold`
- `feature_branch`: `codex/pause-run-for-human-approval`

当前 Human Approval 已持久化且 Java 能执行批准后的批次冻结，但 Agent Run 仍停留在 `RUNNING`，无法表达“等待人工批准”的真实检查点。此 Change 在首次保存 PENDING Approval 的同一 Agent MySQL 事务内，把来源 Run 从 `RUNNING` 推进到 `WAITING_FOR_APPROVAL` 并写入确定性 transition fact；Approval 与 Run 必须同成同败、相同请求可重放、冲突状态 fail closed。

非目标：不轮询 Java Approval API，不恢复已批准 Run，不执行业务动作，不完成 Coordinator Execution/Run，不增加 Kafka/UI，不修改 `dataset/`。

学习等级 `deep`：首次跨 Agent 聚合原子协调 Approval 与 Run lifecycle，并冻结新的锁序和恢复语义。Owner Review/Learning 延后至 demo milestone。本 Change 是 demo 路线第 6/10 个，完成后最多剩 4 个。
