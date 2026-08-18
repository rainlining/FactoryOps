# Worker Task Execution Start 规格增量

## ADDED Requirements

### Requirement: 只有有效 lease owner 可以启动 Task

系统必须同时匹配 task、owner、token 和未过期时间；缺失、陈旧、错误或过期 lease 必须拒绝且不得留下部分写入。

### Requirement: Task 与 Execution 必须原子启动

启动必须在同一事务创建 Specialist Execution 的 PENDING/RUNNING history，并把 PENDING Task 推进为 RUNNING、引用该 Execution 和 attempt 1。

#### Scenario: history 写入失败
- **WHEN** 任一 Execution 或 Task history 写入失败
- **THEN** Task、Execution 和启动请求事实全部回滚

### Requirement: 依赖必须 ready

只有所有直接依赖均为 SUCCEEDED 的 PENDING Task 可启动。

### Requirement: 启动请求必须幂等

相同 request 与相同命令返回 identical；相同 request 与不同命令返回 conflicting；两者都不得创建第二个 Execution。
