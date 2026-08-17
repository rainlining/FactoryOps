# Change 学习计划

- `learning_level`: `deep`
- `gate_status`: `not-started`

Review 需解释 owner/token/expiry、安全释放和为何 lease 不等于 Task RUNNING。Owner 修改：调整 TTL 上限边界并运行测试。Failure exercise：注入过期 lease 与陈旧 token，观察旧 owner 不能释放新 owner 的 lease。
