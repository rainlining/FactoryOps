# Change 提案：只读 Workflow Snapshot 查询

- `change_id`: `2026-08-21-demo-query-api`
- `status`: `review-handoff-ready`
- `learning_level`: `standard`
- `depends_on`: `2026-08-21-complete-approved-action-workflow`

个人演示需要在一次查询中说明质量事件触发的 Run、Specialist Tasks、Coordinator、Fusion、Risk、Approval 是否形成完整闭环。本 Change 提供只读 `WorkflowSnapshotQueryService`，按 `run_id` 返回确定性、脱敏且可序列化的快照；Java Business Receipt 跨数据库聚合留给后续 adapter。

非目标：不改变任何业务状态；不执行 Risk/Approval/Business Action；不读取 `dataset/`；不新增认证、分页、实时推送或 dashboard UI。
