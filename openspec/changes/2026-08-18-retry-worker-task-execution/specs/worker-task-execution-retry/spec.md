# Worker Task Execution Retry 规格增量

## ADDED Requirements

### Requirement: 只有有效 lease owner 可以重试当前 attempt

Task 与 Execution 必须是 current RUNNING pair，且 owner、token 和 expiry 匹配；否则拒绝且无部分写入。

### Requirement: retry 必须原子替换 attempt

系统必须在同一事务把当前 Execution 置 FAILED/retryable、创建 attempt+1 的 RUNNING Execution、把 Task 以 RUNNING→RUNNING 切换到新 Execution，并保留 lease。

#### Scenario: 任一 history 写入失败
- **WHEN** 旧 Execution、新 Execution 或 Task 的任一 history 写入失败
- **THEN** 当前 Task/Execution/lease 与 retry request 均保持原状

### Requirement: 只有安全分类且未耗尽的失败可以重试

failure code 必须属于冻结的安全技术错误集合，recoverability 必须为 retryable，且当前 attempt 必须小于 max attempts；否则拒绝。

### Requirement: retry request 必须并发幂等

相同 request/command 返回 identical；相同 request/不同 command 返回 conflicting。相同 request 跨 Task 并发时只允许一个 applied，输家不改变状态。
