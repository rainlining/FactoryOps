# Quality Incident Opened Event Contract 规格增量

## 新增需求

### Requirement: 事件必须表达已经成立的 Incident 事实

事件类型必须为 `quality.incident.opened`，Contract 版本必须为 `1.0`。它只表示 Quality Incident 已由 Java 事务成功创建并处于 OPEN，不表示模型刚完成推理，也不要求 Consumer 创建 Incident。

### Requirement: 事件身份必须由业务事实稳定派生

`event_id` 必须为 `EVT-` 加完整大写 SHA-256；摘要输入固定为 `factoryops:event:quality.incident.opened:v1:<incident_id>`。同一 Incident 的发布重试、Outbox replay 和 Kafka redelivery 必须保持相同 event_id 与 canonical payload。

### Requirement: 事件必须只携带必要的不可变引用

payload 必须包含 Incident schema version、Incident ID、status、Batch ID、Inspection ID 和 Result ID。不得复制 anomaly score、threshold、model、Artifact、Result origin、当前 Batch 状态或 Evaluation ground truth。

### Requirement: 事件必须区分事件时间与发布时间

`occurred_at` 必须等于 Incident `created_at`，代表业务事实发生时间。Contract 不包含 `published_at`；Kafka 发布尝试时间属于 Outbox/Producer 可观测性，不得改写业务事件。

### Requirement: 事件生产者和关联信息必须可追溯

envelope 必须声明 producer name/version、aggregate type/id，并以 Incident ID 作为 `correlation_id`。`causation_id` 必须引用触发 Incident 的 Result ID。

### Requirement: Kafka 路由必须稳定

topic 固定为 `factoryops.quality.incident.v1`，message key 固定为 `incident_id`。同一 Incident 的事件因此进入同一 partition；Contract 不承诺不同 Incident 的全局顺序。

### Requirement: v1.0 Consumer 必须严格校验

Schema 必须禁止未知字段，只接受 contract version `1.0`、event type `quality.incident.opened`、OPEN status 和 UTC RFC 3339 时间。非法输入必须在进行关系分类或业务处理前被拒绝。

### Requirement: Event Contract 必须支持确定性关系分类

完全相同 event_id 和 canonical payload 分类为 `duplicate-identical`；相同 event_id 但内容不同分类为 `duplicate-conflicting`；不同 event_id 分类为 `distinct`。非法事件不产生关系分类。

### Requirement: 版本演进不得静默扩展严格 Consumer

v1.0 不接受新增字段。任何字段变化必须发布明确的新 Contract 版本；破坏性变化必须使用新的 major topic。Producer 不得假设旧 Consumer 会忽略未知字段。
