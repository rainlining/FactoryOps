# 设计：Human Approval Contract

Approval identity 绑定 Risk Decision v1.1 的 decision/fusion/run identity；`approval_key = SHA256("v1\n<decision_key>")`，相同 Decision 只能有一个审批流。request 区复制 proposed action、risk level、policy/reason provenance 和请求/过期时间，公开 validator 必须与完整源 Risk Decision 逐字段比对，且源 Gate 必须为 `REQUIRE_APPROVAL`。

状态快照包含 revision 与 status。revision 1 必须是 PENDING 且不含 outcome；下一 revision 只允许 PENDING→APPROVED/REJECTED/EXPIRED。APPROVED/REJECTED 必须由 HUMAN actor 在 `expires_at` 前决定；到达 `expires_at` 的瞬间起只允许 SYSTEM EXPIRED。终态不可继续迁移。审批批准只证明人工 Gate 通过，不表示业务动作已经执行。

canonical 对无序 policy/reason codes 排序并归一化数字；relation 区分 identical、合法 next revision、conflicting 和 distinct。Contract 不持久化模型原文、ground truth 或敏感显示名。

测试覆盖合法 pending/approved、源绑定、非法来源 Gate、key、时间、actor/status、revision 状态边、canonical 和 ground-truth 拒绝。
