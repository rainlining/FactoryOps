# Agent Run Inbox Start 规格

### Requirement: 可信 Inbox 事件必须在 offset commit 前拥有 original Run

`accepted` 与 `duplicate-identical` 的 `quality.incident.opened` 事件都必须确保唯一 original Run 已存在。Run 创建或确认失败时不得提交当前 Kafka offset。

#### Scenario: 首次事件创建 Run

- **WHEN** 首次可信事件成功写入 Inbox
- **THEN** 系统创建 `PENDING / revision 0` original Run 与初始 history
- **AND** 完成后才提交 record 的 `offset + 1`

#### Scenario: Inbox 已提交但 Run 尚未创建

- **GIVEN** Inbox commit 后、Run 创建前发生故障
- **WHEN** Kafka 重投相同 record
- **THEN** Inbox 返回 `duplicate-identical`
- **AND** 系统仍必须补建 Run 后才提交 offset

### Requirement: Starter 必须沿用已冻结的 Run

已有同一 `trigger_event_id` 的 Run 且 Incident 一致时，Starter 必须返回 `already-started`，不得使用当前启动配置覆盖已有 Provenance。

#### Scenario: 部署配置跨越

- **GIVEN** 旧版本服务已经创建 Run 但尚未提交 offset
- **AND** 新版本服务的 Prompt 或 Model 配置不同
- **WHEN** 新版本处理 Kafka 重投
- **THEN** 沿用原 Run 与原 Provenance
- **AND** 允许提交 offset

#### Scenario: 事件与已有 Run 的 Incident 不一致

- **WHEN** 同一 trigger event 的已有 Run 属于另一个 Incident
- **THEN** 返回不可重试完整性错误
- **AND** 不提交 offset或修改已有 Run

### Requirement: Provenance 必须来自经过验证的启动配置

Incident ID 必须来自已通过 Contract 的 `DecodedEvent`；Runtime、Workflow、Prompt Set、Model Policy、Tool Policy、Context Policy 和代码 revision 必须来自启动时冻结的配置。

#### Scenario: 配置缺失或非法

- **WHEN** 任一必要版本配置缺失、为空或格式非法
- **THEN** Agent Service 必须在创建 Kafka Consumer 前启动失败

### Requirement: 非可信 Inbox 结果不得启动 Run

`rejected-invalid` 与 `rejected-conflicting` 只保留 rejection 证据，不得创建 Run；证据事务成功后允许提交 offset。

### Requirement: 失败必须按可恢复性分类

临时数据库或 Kafka 适配器失败必须保留当前 offset 并重试；确定性配置或持久化完整性错误必须停止进程，禁止无限重试或提交 offset。

### Requirement: Run 启动结果必须可观察

处理结果和日志必须包含可选 Run ID 以及 `created`、`already-started` 或 `not-applicable`，不得记录完整 payload。
