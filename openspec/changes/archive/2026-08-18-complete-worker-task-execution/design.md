# Change 设计：完成 Worker Task Execution

`complete` 按 completion request-key named advisory lock → completion request → Task → lease → Execution 固定顺序锁定。它验证 Task/Execution 是 current RUNNING pair 和 lease 未过期，再先更新 Execution/history、后更新 Task/history、条件删除 lease并保存 request fingerprint。任一步失败由 MySQL 回滚全部状态。

SUCCEEDED 只接受 result；FAILED 只接受 `non_retryable` failure，以满足 Task Contract。retryable failure 需要新 attempt、lease 与 retry policy，不在当前范围。重放先读 request fact，因此 lease 已删除后仍能返回稳定结果。

advisory lock 名称从 completion request ID 的 SHA-256 派生，在业务事务外取得并在 `finally` 显式释放；它只串行化相同 request key，Task/lease/Execution 行锁仍负责 ownership 和状态。缺失 request 行的 `FOR UPDATE` 无法稳定串行化不同 Task 的并发 insert，因此不能只依赖主键冲突恢复。

真实 MySQL 测试覆盖成功、不可重试失败、顺序与并发重放、跨 Task request 冲突、错误 owner 和 history 注入回滚。
