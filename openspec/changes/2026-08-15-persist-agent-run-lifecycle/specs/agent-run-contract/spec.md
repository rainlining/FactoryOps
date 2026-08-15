# Agent Run Contract 规格修正

## MODIFIED Requirements

### Requirement: Lifecycle 必须使用受限状态和一致时间语义

状态必须属于 `PENDING`、`RUNNING`、`WAITING_FOR_APPROVAL`、`SUSPENDED`、`SUCCEEDED`、`FAILED`、`CANCELLED`。后三者必须是终态。

#### Scenario: 非终态快照

- **WHEN** Run 处于非终态
- **THEN** 不得具有 `ended_at`

#### Scenario: 成功或失败终态

- **WHEN** Run 处于 `SUCCEEDED` 或 `FAILED`
- **THEN** 必须具有 `started_at` 和 `ended_at`
- **AND** `ended_at` 不得早于 `started_at`

#### Scenario: 启动前取消

- **WHEN** Run 从 `PENDING` 进入 `CANCELLED`
- **THEN** 必须具有 `ended_at`
- **AND** 允许没有 `started_at`

#### Scenario: 启动后取消

- **WHEN** 已启动 Run 进入 `CANCELLED`
- **THEN** 必须保留已有 `started_at`
- **AND** 必须具有 `ended_at`
