# 技术设计：Quality Incident Opened Event Contract v1.0

## 1. 结论

第一份跨边界事件选择 `quality.incident.opened`，而不是 `quality.anomaly_detected`。Java 已经在同一事务中保存异常 Result、完成 Inspection 并创建 Incident；因此对 Agent World 最准确的事实是“可处理的问题单已经成立”。Consumer 只需以 Incident 为入口启动后续工作，不重复创建业务对象。

本 Change 只冻结 Contract，不连接 Kafka。这样可将四个问题独立 review：

```text
事件说什么 → Outbox 如何原子保存 → Producer 如何发布 → Consumer 如何幂等处理
```

## 2. Envelope 与 Payload

推荐结构：

```json
{
  "contract_version": "1.0",
  "event_id": "EVT-<64 uppercase hex>",
  "event_type": "quality.incident.opened",
  "occurred_at": "2026-08-14T01:02:03.123456Z",
  "producer": {
    "name": "factoryops-business-service",
    "version": "0.1.0"
  },
  "aggregate": {
    "type": "quality-incident",
    "id": "QI-<64 uppercase hex>"
  },
  "correlation_id": "QI-<64 uppercase hex>",
  "causation_id": "result-1001",
  "payload": {
    "incident_schema_version": "1.0",
    "incident_id": "QI-<64 uppercase hex>",
    "status": "OPEN",
    "batch_id": "B-17",
    "inspection_id": "inspection-00731",
    "result_id": "result-1001"
  }
}
```

Envelope 负责传输语义和追踪；payload 负责业务事实。`aggregate.id`、`correlation_id` 与 `payload.incident_id` 必须相等，`causation_id` 与 `payload.result_id` 必须相等。

## 3. 字段取舍

事件保留三个证据 ID，使 Agent Runtime 能定位 Incident、Batch、Inspection 和原 Result，但不复制模型观察详情。原因是 Result 已经不可变，复制 score/model/artifact 会形成两个事实来源，并让事件随 Vision Contract 变化。

不携带 `result_origin_kind`。它是查询视图中的派生信息，不属于 Incident 自身；Agent 若需要，应通过版本化 Business API 加载 Context。

不携带 Batch 当前 status。Incident 创建不改变 Batch；事件发布可能延迟，嵌入“当前状态”很快过时。

不携带 `published_at`。Outbox 可能多次尝试发布，发布时间是传输可观测性而非不可变业务事实。

## 4. 身份、重复与 Replay

```text
event_id = "EVT-" + UPPER_HEX(SHA-256(
  "factoryops:event:quality.incident.opened:v1:" + incident_id
))
```

确定性 ID 使首次发布、Producer retry、人工 replay 和 Kafka redelivery 指向同一事件事实。Outbox 后续必须保存生成时的完整 canonical payload；replay 只能重新发送原 payload，不能读取最新数据库状态后重建。

关系分类：

- 同 ID + 同 canonical payload：`duplicate-identical`；
- 同 ID + 不同 payload：`duplicate-conflicting`，属于数据完整性故障；
- 不同 ID：`distinct`；
- Schema/语义非法：先拒绝，不分类。

## 5. 时间语义

`occurred_at = QualityIncident.created_at`。它回答“问题单何时成立”，不回答“Kafka 何时收到消息”。Outbox 积压或重放不能修改 occurred_at，否则 SLA、Replay 和审计会把传输延迟误认为业务发生时间。

时间只接受 UTC `Z` 形式的 RFC 3339，允许 0～6 位小数秒，与 MySQL `TIMESTAMP(6)` 对齐。

## 6. Kafka 路由

- Topic：`factoryops.quality.incident.v1`
- Message key：`incident_id`
- Value：严格符合本 JSON Contract 的 UTF-8 JSON

Topic 名携带 major version，而 event envelope 携带精确 contract version。相同 Incident 使用相同 key，保证其事件在同一 partition 内有序；系统不依赖跨 Incident 全局顺序。

本 Change 不创建 topic，也不决定 partition 数、replication factor、retention 或压缩策略，这些属于 Kafka Backbone 部署 Change。

## 7. 版本演进

v1.0 使用 `additionalProperties: false`，旧 Consumer 不静默接受未知字段。新增字段也必须发布显式版本，并由 Consumer 明确声明支持。删除字段、改变含义或类型属于 major breaking change，必须使用新的 major topic，允许新旧版本并行迁移。

## 8. 安全边界

事件不包含图片内容、大型 Artifact、Prompt、Agent Context、凭据、个人信息或 Evaluation ground truth。Kafka 只连接 Business World 与 Agent World，不作为 Agent 间聊天通道。

## 9. 被放弃的方案

- `quality.anomaly_detected`：容易让 Consumer 误以为 Incident 尚未创建。
- 同时发布 anomaly 与 incident 两种事件：当前没有两个独立消费者需求，会制造重复事实和顺序问题。
- 随机 event_id：使重试和 replay 必须额外查找首次身份。
- 将完整 Result 嵌入事件：扩大耦合并复制事实。
- 使用 Batch ID 作为 key：会把同 Batch 的流量集中，但当前工作流 owner 是 Incident，且会掩盖 Incident 级顺序。
- 宽松接受未知字段：与项目当前严格 Consumer 策略冲突，降低可解释性。

## 10. 后续 Change 的约束

Outbox 必须在创建 Incident 的同一 MySQL 事务保存 event_id、topic、message key、contract version、event type、occurred_at 和 immutable payload。Producer 只能发布 Outbox 已保存内容。Consumer 必须假设 at-least-once，先验证 Contract，再以 event_id 执行幂等接收。
