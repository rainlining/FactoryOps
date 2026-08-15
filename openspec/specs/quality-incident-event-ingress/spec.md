# Quality Incident Event Ingress 规格

### Requirement: Consumer 必须属于 Agent World

`quality.incident.opened` Consumer 必须运行在 Python Agent Service 中。当前入口只能产生持久化 Inbox 事实，不得启动 Coordinator、调用模型或修改 Java 业务表。

### Requirement: Consumer 必须显式控制 offset

Consumer 必须关闭自动 offset commit 和自动 offset store，使用固定版本化 Group ID。只有当前 Kafka record 已获得持久化处理结果后，才能同步提交该 record 的 `offset + 1`。

### Requirement: 失败记录不得被更高 offset 越过

数据库处理失败或 offset 提交失败时，Consumer 必须 seek 回当前 topic/partition/offset，不得继续处理并提交同一 Partition 的更高 offset。若 rebalance 已使当前实例失去 Partition，必须放弃本地 seek，由新 owner 从已提交 offset 恢复。

### Requirement: 有效事件必须经过冻结 Contract 与路由校验

Consumer 必须依次验证 UTF-8、JSON object、`quality_incident_opened/v1.0` Contract，并要求 Kafka key 等于事件 `payload.incident_id`。验证不得读取 Evaluation ground truth。

### Requirement: 首次事件必须持久化到 Agent Inbox

首次有效 `event_id` 必须在单个 MySQL 事务中写入 Agent 自有 Inbox，保存 event ID、event type、contract version、topic、partition、offset、message key、原始 payload bytes、canonical SHA-256 和数据库接收时间。Inbox 不得写入 Java 业务表。

### Requirement: 相同事件必须幂等

已存在相同 `event_id` 且 canonical hash 相同的消息必须分类为 `duplicate-identical`，不得创建第二条 Inbox。该结果视为已持久化，可以提交当前重复 record 的 offset。

### Requirement: 冲突与非法消息必须持久化隔离证据

相同 `event_id` 但 canonical hash 不同的有效消息必须分类为 `duplicate-conflicting`。非法 UTF-8、JSON、Contract 或 message key 必须分类为 invalid。两类消息都必须用 topic/partition/offset 唯一记录 reason code、可选 event ID 和 payload SHA-256，但不得保存原始非法 payload；隔离事务成功后允许提交 offset。

### Requirement: Inbox 与 offset 必须形成明确的 at-least-once 顺序

顺序必须是 MySQL commit 在前、Kafka offset commit 在后。MySQL 已成功而 offset commit 失败时允许重投；重投必须由 Inbox 幂等吸收。系统不得宣称 MySQL 与 Kafka offset 原子提交或 exactly-once。

### Requirement: 消费行为必须可观察

日志必须包含 topic、partition、offset、event ID（可得时）、处理结果、数据库耗时和 offset commit 结果，不得记录完整 payload。自动化测试必须能检查 committed offset、Inbox 数量和 rejection 数量。
