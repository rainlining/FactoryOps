# Change 提案：完成已批准动作的 Agent Workflow

- `change_id`: `2026-08-21-complete-approved-action-workflow`
- `status`: `review-handoff-ready`
- `learning_level`: `standard`
- `depends_on`: `2026-08-21-resume-approved-action-execution`
- `feature_branch`: `codex/complete-approved-action-workflow`

前一 Change 已把真实批准动作执行并将 Run 恢复为 `RUNNING`，但 Coordinator Execution 与 Run 仍不会进入成功终态，产品无法展示一条完整结束的审计链。本 Change 在确认所有 Specialist Task 成功、Fusion/Risk/Approval provenance 完整、Java 动作回执有效后，原子完成 Coordinator Execution 与 Run。

学习等级为 `standard`：复用已完成的 lifecycle CAS、确定性 request identity 和单 MySQL 事务模式；新增点是跨 Coordinator Execution 与 Run 的双聚合原子收口及全图 readiness admission。Owner Review/Learning 延后至 demo milestone。本 Change 是 demo 路线第 8/10 个。

非目标：不新增触发入口/UI，不处理 REJECTED/EXPIRED/失败收口，不执行第二次业务动作，不修改 Worker/Task 结果，不修改 `dataset/`。
