# Worker Task Execution Completion 规格增量

## ADDED Requirements

### Requirement: 只有当前有效 owner 可以完成

Task/Execution 必须是同一 RUNNING pair，且 task、owner、token、expiry 全部匹配。

### Requirement: Execution 与 Task 必须原子收口

成功必须把双方置 SUCCEEDED 并保存 result；不可重试失败必须把双方置 FAILED 并保存一致 failure。双方 snapshot/history、completion request 和 lease 删除必须在同一事务。

#### Scenario: history 失败
- **WHEN** 任一 completion history 写入失败
- **THEN** Task/Execution 保持 RUNNING，lease 保留，请求事实不存在

### Requirement: 完成请求必须幂等

相同请求和命令返回 identical；相同请求不同命令返回 conflicting；终态和 history 不得重复写入。

### Requirement: retryable failure 不得伪装为终态

本能力拒绝以 retryable failure 把 Task 置 FAILED；新 attempt 由独立 retry policy Change 负责。
