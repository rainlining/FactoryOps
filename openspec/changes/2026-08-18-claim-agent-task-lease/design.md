# Change 设计：Task Lease

`AgentTaskLeaseService` 负责参数与 ownership 语义；`agent_task_leases` 保存独立事实。claim 锁 Task 行后锁 lease 行，检查 PENDING 与 expiry，再插入或更新；renew 使用 owner/token/未过期条件 UPDATE；release 使用 owner/token DELETE。Task 事务与 lease 事务分离，避免 lease 改写生命周期。

失败路径包括非 PENDING、未过期竞争、陈旧 token、续租超时和删除竞态。所有写入依靠 InnoDB 条件与 FK；没有 Redis 或跨库事务。
