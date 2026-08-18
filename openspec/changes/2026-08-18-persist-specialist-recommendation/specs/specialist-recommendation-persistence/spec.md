# Specialist Recommendation Persistence 规格增量

## ADDED Requirements

### Requirement: 只有 current RUNNING Specialist Execution 可以首次保存建议

Recommendation 的 execution/run/task/role 必须与数据库中的 current RUNNING Execution/Task 一致；缺失、终态或错配必须拒绝且无写入。

### Requirement: Recommendation 必须保存为不可变 canonical 事实

系统必须保存严格 Contract canonical JSON、SHA-256 和查询列；读取必须重新验证 Contract，损坏数据不得尽力返回。

### Requirement: 保存必须幂等并支持并发

相同 recommendation key 与 canonical payload 返回 identical；相同 key 不同 payload 或同 recommendation ID 不同 key 返回 conflicting；并发只能留下一个事实，不得泄漏数据库异常。

### Requirement: 持久化不得推进执行状态

保存 Recommendation 不得修改 Execution、Task 或 lease；Execution Completion 属于独立事务和 Change。
