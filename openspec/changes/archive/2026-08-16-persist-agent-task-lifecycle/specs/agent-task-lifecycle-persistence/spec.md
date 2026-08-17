# Agent Task Lifecycle Persistence 规格增量

## ADDED Requirements

### Requirement: Task 创建必须持久、幂等且原子

系统必须以 `task_request_id` 作为创建请求幂等键，在同一 MySQL 事务写入 Task snapshot、依赖关系和 revision 0 初始历史。

#### Scenario: 首次创建

- **WHEN** 合法创建请求引用已存在 Run 和合法依赖
- **THEN** 创建一个 PENDING Task、全部依赖和一条 revision 0 history

#### Scenario: 相同请求重投

- **WHEN** 相同 `task_request_id` 和相同不可变内容再次提交
- **THEN** 返回 `duplicate-identical` 且不增加行

#### Scenario: 冲突请求重投

- **WHEN** 相同 `task_request_id` 携带不同不可变内容
- **THEN** 返回 `duplicate-conflicting` 且保留首次事实

#### Scenario: 初始历史失败

- **WHEN** snapshot 已插入但初始 history 写入失败
- **THEN** 整个事务回滚且 Task 与依赖均不可见

### Requirement: Task 依赖必须可验证

每个依赖 Task 必须存在、属于同一个 Run，并且不得是自身或重复引用。

#### Scenario: 缺失或跨 Run 依赖

- **WHEN** 创建请求引用不存在或其他 Run 的 Task
- **THEN** 拒绝整个创建请求且不留下部分数据

#### Scenario: 自依赖

- **WHEN** 创建请求使用即将创建的 `task_id` 作为依赖
- **THEN** 拒绝创建

### Requirement: 生命周期迁移必须受幂等和乐观锁保护

系统必须以 `transition_request_id` 幂等，并仅在 `task_id + expected_status + expected_revision` 同时匹配时更新 snapshot 和追加 history。

#### Scenario: 合法迁移

- **WHEN** expected status/revision 匹配且目标状态、attempt 和结果满足 Contract
- **THEN** snapshot revision 加一并追加恰好一条 history

#### Scenario: 相同迁移重投

- **WHEN** 同一 transition request 和相同命令再次提交
- **THEN** 返回 `duplicate-identical` 且不重复追加 history

#### Scenario: transition request 冲突

- **WHEN** 同一 transition request 携带不同命令
- **THEN** 返回 `duplicate-conflicting` 且保留首次事实

#### Scenario: stale revision 并发

- **WHEN** 两个不同请求竞争同一 expected revision
- **THEN** 最多一个为 `applied`，其他为 `concurrency-conflict`

#### Scenario: history 失败

- **WHEN** snapshot 更新后 history 插入失败
- **THEN** snapshot 更新回滚

### Requirement: 状态、时间和 attempt 必须满足 Task Contract

系统必须支持 Contract 定义的状态图；首次 RUNNING 建立 started_at 和 attempt 1，RUNNING→RUNNING 表示新 attempt，终态记录 ended_at，并拒绝终态离开、时钟回退和不一致 completion/failure。

#### Scenario: retry attempt

- **WHEN** RUNNING Task 以新的 Execution ID 迁移到 RUNNING
- **THEN** attempt_count 恰好加一且 started_at 保持不变

#### Scenario: 成功或失败

- **WHEN** Task 进入 SUCCEEDED 或 FAILED
- **THEN** 对应 completion 或 failure 引用当前 Execution，另一结果为空

#### Scenario: 取消或跳过

- **WHEN** PENDING Task 进入 CANCELLED 或 SKIPPED
- **THEN** ended_at 被记录且无需 started_at 或 Execution

#### Scenario: 终态离开或时钟回退

- **WHEN** 请求离开终态，或新的时间早于已持久时间
- **THEN** 拒绝且 snapshot/history 不变

### Requirement: 数据库读取必须重建严格 Contract

Repository 读取必须从结构化列与引用表重建 Agent Task v1.0.0 Contract，并调用 `contracts.agent_task.validator.validate_task`。

#### Scenario: 持久化数据破坏 Contract

- **WHEN** 数据库数据无法重建合法 Task Contract
- **THEN** 抛出明确的持久化完整性错误，不返回尽力而为结果
