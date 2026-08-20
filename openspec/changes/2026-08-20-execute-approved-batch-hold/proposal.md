# Change 提案：执行已批准的批次冻结

- `change_id`: `2026-08-20-execute-approved-batch-hold`
- `status`: `applying`
- `learning_level`: `deep`
- `depends_on`: `2026-08-20-bind-approval-action-target`
- `feature_branch`: `codex/execute-approved-batch-hold`

本 Change 将 APPROVED、incident-bound 的 Human Approval 转化为首个真实且可展示的业务副作用：`HOLD_BATCH`。Business Service 只能从 Approval 的 `incident_id` 解析 Quality Incident、Inspection、Result 与 Batch，不接受调用者提供目标；审批、执行收据与 Batch hold 在同一事务内完成并支持幂等重放。

非目标：不执行 `STOP_LINE`/`REJECT_ITEM`，不推进 Agent Run/Task，不发布 Kafka completion，不修改 Agent Contract，不创建 UI，不修改 `dataset/`。

学习等级 `deep`：首次把 LLM 建议经 Risk/Approval 转化为真实业务副作用，新增权限 fencing、跨聚合事务与幂等执行语义。Owner Review/Learning 延后至 demo milestone。本 Change 是 demo 路线第 5/10 个，完成后最多剩 5 个。
