# Change 提案：绑定 Approval 动作目标

- `change_id`: `2026-08-20-bind-approval-action-target`
- `status`: `review-handoff-ready`
- `learning_level`: `deep`
- `depends_on`: `2026-08-20-operate-human-approval`
- `feature_branch`: `codex/bind-approval-action-target`

Human Approval v1.0 只批准动作类型和 Run，没有在审批事实中保存原始 Quality Incident。若执行端再接受调用者提供的 Batch/Line，批准可能被复用于错误目标。本 Change 发布 Human Approval v1.1，在 identity 中加入 `incident_id`，由 Agent persistence 在同一事务验证 `approval.run_id → agent_runs.incident_id`，并让 Java Approval API 只接受可执行的 v1.1 新审批。

非目标：不执行业务动作、不修改 Specialist/Fusion/Risk Contract、不从 evidence refs 猜目标、不新增跨服务同步调用、不推进 Workflow、不修改 `dataset/`。

学习等级 `deep`：引入新的权限/provenance 不变量并跨 Python/Java 两个持久化边界保持兼容。Owner Review/Learning 延后至 demo milestone。本 Change 是 demo 路线第 4/10 个，完成后最多剩 6 个。
