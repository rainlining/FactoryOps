# 技术选型：启动 Worker Task Execution

- 选择 MySQL 单事务和行锁，复用当前 Agent Service 的持久化边界。
- 选择独立 request 表保存幂等事实，不能从最终状态可靠推断 request identity。
- 放弃顺序调用 Execution/Task Service，因为任一第二步失败都会留下部分提交。
- 放弃 Redis 锁；Task 与 lease 已在同一 MySQL 一致性域。
- request-key 并发采用 MySQL named advisory lock；缺失 request 行无法靠 `FOR UPDATE` 稳定串行化并发 insert，而独立 admission 表会引入事务外持久事实和清理语义。
