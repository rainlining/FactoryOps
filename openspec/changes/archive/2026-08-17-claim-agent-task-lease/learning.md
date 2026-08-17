# Change 学习计划

- `learning_level`: `deep`
- `gate_status`: `completed-externally`

Review 需解释 owner/token/expiry、安全释放和为何 lease 不等于 Task RUNNING。Owner 修改已由 Codex 按项目所有者授权完成：真实 MySQL 测试确认 TTL=3600 可接受、TTL=3601 被拒绝。Failure exercise 已完成：过期 lease 由 worker-2 接管后，worker-1 的旧 token 不能 renew/release，worker-2 lease 保持。

项目所有者已说明 Learning Gate 在其他地方完成，本会话不再阻塞于 Owner 修改的执行主体。
