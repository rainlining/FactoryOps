# Change 提案：持久化 Human Approval

- `change_id`: `2026-08-20-persist-human-approval`
- `status`: `review-handoff-ready`
- `learning_level`: `deep`
- `depends_on`: `2026-08-20-define-human-approval-contract`
- `feature_branch`: `codex/persist-human-approval`

Human Approval Contract 已冻结，但审批请求与终态仍不能可靠保存。本 Change 用 MySQL 保存当前快照和不可变 revision history，绑定真实 `REQUIRE_APPROVAL` Risk Decision，支持并发幂等、乐观 revision 和损坏读取拒绝。

非目标：不提供 HTTP/UI、不实现认证目录/通知、不推进 Run/Execution、不调用 Java Business API、不执行业务动作、不修改 `dataset/`。

学习等级 `deep`：首次实现人工状态的事务、并发决胜与审计 history。Owner Review/Learning 延后至 demo milestone。本 Change 是 demo 路线第 2/10 个，完成后最多剩 8 个。
