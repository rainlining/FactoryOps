# 技术选型：完成 Worker Task Execution

- 继续使用 MySQL 单事务，保持与 start 相同的一致性域。
- lease 删除放在 snapshot/history 成功之后但仍在同一事务，避免失败后丢失 ownership。
- 只允许不可重试失败进入 Task FAILED；retryable failure 留给独立 retry Change。
- request 表保存命令指纹和结果引用，使 lease 删除后的 replay 仍可分类。
