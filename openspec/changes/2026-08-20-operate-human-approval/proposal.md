# Change 提案：运行 Human Approval API

- `change_id`: `2026-08-20-operate-human-approval`
- `status`: `review-handoff-ready`
- `learning_level`: `deep`
- `depends_on`: `2026-08-20-persist-human-approval`
- `feature_branch`: `codex/operate-human-approval`

Agent 侧已经能形成并保存待审批事实，但产品还没有由 Java Business Backend 所有的确定性人工审批入口。本 Change 提供创建、查询、批准和拒绝 REST API，用服务端 allowlist 解析 actor 身份，以行锁保证 PENDING 只能产生一个终态，并保留不可变 revision history。

非目标：不执行 STOP_LINE/HOLD_BATCH/REJECT_ITEM，不推进 Agent Run，不发布 Kafka 事件，不实现企业 SSO/RBAC 管理后台，不修改 Agent 侧 `human_approvals` 表，不修改 `dataset/`。审批完成事件与 Workflow 恢复在后续编排 Change 中实现。

学习等级 `deep`：首次在 Java 业务边界实现人工权限、状态机、幂等和审计事务。Owner Review/Learning 延后至 demo milestone。本 Change 是 demo 路线第 3/10 个，完成后最多剩 7 个。
