# Agent Run Lifecycle Persistence 规格增量

## ADDED Requirements

### Requirement: Run 当前快照与迁移历史必须共同持久化

系统必须在 `agent_runs` 保存当前快照，并在 `agent_run_transitions` 保存不可覆盖的迁移历史。创建和迁移涉及的两张表写入必须共享一个 MySQL 事务。

#### Scenario: original Run 原子创建

- **WHEN** 一个已持久化 Inbox 事件首次创建 original Run
- **THEN** 系统必须写入 `PENDING / revision 0` Run
- **AND** 同事务写入 `NULL → PENDING` 初始 history
- **AND** 任一 INSERT 失败时两张表均不得留下记录

### Requirement: original 与 replay 创建必须幂等

系统必须以 `trigger_event_id` 唯一标识 original 创建，以 `replay_request_id` 唯一标识 replay 创建。

#### Scenario: 相同创建请求重试

- **WHEN** 相同幂等键和相同调用方不可变输入再次提交
- **THEN** 返回已有 Run 和 `duplicate-identical`
- **AND** 不创建第二个 Run 或初始 history

#### Scenario: 幂等键被不同内容复用

- **WHEN** 相同幂等键携带不同 Provenance 或 replay 血缘
- **THEN** 返回 `duplicate-conflicting`
- **AND** 不修改已有 Run

### Requirement: replay 必须保持同 Incident 的合法血缘

系统必须验证根 Run 是 original、直接来源属于同一根血缘，且根、来源和新 replay 的 `incident_id` 相同。

#### Scenario: 引用另一个 Incident 的来源

- **WHEN** replay 的根 Run 与直接来源属于不同 Incident
- **THEN** Application Service 必须在写入前拒绝

### Requirement: 状态迁移必须使用乐观锁

迁移必须同时匹配 `run_id`、`expected_status` 和 `expected_revision`，成功后 revision 精确增加 1。冲突不得自动重试业务决定。

#### Scenario: 两个执行者并发迁移

- **GIVEN** 两个命令都基于相同 status 和 revision
- **WHEN** 它们并发提交不同目标状态
- **THEN** 最多一个命令可以成功
- **AND** 失败命令返回 `concurrency-conflict`
- **AND** 当前快照与 history 保持连续

### Requirement: 迁移请求必须可安全重试

每次迁移必须携带稳定 `transition_request_id` 并由唯一约束保护。写事务失败后的分类查询必须在新事务中执行。

#### Scenario: 提交成功但响应丢失

- **WHEN** 调用方使用相同请求 ID 和相同命令重试
- **THEN** 返回 `duplicate-identical`
- **AND** 不重复增加 revision

#### Scenario: 请求 ID 被不同命令复用

- **WHEN** 同一请求 ID 携带不同 Run、目标状态、Actor、Reason 或 Checkpoint
- **THEN** 返回 `duplicate-conflicting`

### Requirement: 状态迁移必须遵守确定性状态图

系统只允许设计中列出的迁移，终态不得离开。进入 `SUSPENDED` 必须提供 Checkpoint 引用和稳定原因。

#### Scenario: 终态再次迁移

- **WHEN** `SUCCEEDED`、`FAILED` 或 `CANCELLED` Run 收到迁移请求
- **THEN** 在执行 SQL 更新前拒绝

### Requirement: 时间和原因必须保持一致

每次操作必须由应用 UTC Clock 生成一次时间，并在当前快照和 history 中复用。初始 `PENDING` 可无状态原因，所有后续状态必须具有 reason code。

#### Scenario: 启动前取消

- **WHEN** Run 从 `PENDING` 直接进入 `CANCELLED`
- **THEN** 必须设置 `ended_at`
- **AND** `started_at` 必须保持为空

#### Scenario: 已启动 Run 取消

- **WHEN** 已有 `started_at` 的 Run 进入 `CANCELLED`
- **THEN** 必须保留原 `started_at`
- **AND** 设置 `ended_at`

### Requirement: 服务和数据库所有权必须保持隔离

`incident_id` 必须是跨服务逻辑引用，不得建立到 Java Business DB 的外键。Agent DB 内部的 Inbox、Run、Replay 血缘和 transition 必须使用适当外键与 `ON DELETE RESTRICT`。

#### Scenario: Inbox 事件不存在

- **WHEN** original 创建引用不存在的 `trigger_event_id`
- **THEN** 数据库或 Application Service 必须拒绝创建

### Requirement: 数据库读取必须重建合法 Contract

读取 Run 时必须从结构化列重建 Workflow Run Contract，并执行 Contract Validator。非法持久化数据不得以尽力而为方式返回。

#### Scenario: 数据库快照破坏 Contract

- **WHEN** Repository 无法将列重建为合法 v1.0.0 Contract
- **THEN** 抛出明确的持久化完整性错误
