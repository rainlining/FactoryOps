# Change 提案：2026-08-15-consume-quality-incident-events-idempotently

## 元数据

- `change_id`: `2026-08-15-consume-quality-incident-events-idempotently`
- `status`: `review-handoff-ready`
- `learning_level`: `deep`
- `depends_on`: `[2026-08-14-define-quality-incident-opened-event-contract, 2026-08-14-publish-outbox-events-to-kafka]`
- `spec_refs`: `[quality-incident-opened-event-contract, outbox-kafka-publication]`

## 为什么要做

Business Service 已把 `quality.incident.opened` 事件可靠地发布到 Kafka，但 Agent World 尚无可靠入口。Kafka Consumer 在数据库成功、offset 未提交等失败窗口中会收到重复消息；如果直接启动 Agent Workflow，会重复产生 Run 和副作用。

本 Change 建立 Python Agent Service 的最小 Event Ingress：消费并验证事件，把首次有效事件持久化到 Agent 自有 Inbox，识别相同事件，隔离非法或冲突消息，并且只在持久化结果完成后同步提交 Kafka offset。

## 范围

- 建立最小 Python Agent Service 包和配置边界，不初始化 Coordinator/Agent/LLM。
- 使用显式 Consumer Group、关闭自动提交和自动 offset store。
- 对 UTF-8、JSON、版本化 Contract 和 Kafka message key 进行确定性验证。
- 用 MySQL Agent Inbox 持久化首次有效事件及原始 Kafka provenance。
- 对相同 `event_id` 的相同内容执行幂等确认，对不同有效内容执行冲突隔离。
- 对非法消息写入不包含原始 payload 的拒绝证据，避免 poison message 无限重投。
- 数据库事务成功后同步提交 `offset + 1`；任何处理或提交失败都 seek 回当前 offset。
- 使用真实 Kafka 4.1 与 MySQL 8.4 验证重投递、冲突、非法消息和 offset 行为。

## 非目标

- Coordinator Workflow、Agent Run、Prompt、Context、Tool 或模型调用。
- Redis 幂等、Lease、分布式锁或多 Worker 并发处理。
- Retry Topic、DLQ Topic、退避调度和人工重放 API。
- Kafka exactly-once transaction。
- 修改 Java 业务表或现有事件 Contract。
- Consumer Lag 指标、告警和生产部署编排。

## 学习等级理由

这是第一次实现 Kafka Consumer Group、poll position、committed offset、manual commit、rebalance 影响、at-least-once redelivery 和持久化 Inbox 幂等。它引入与 Producer 不同的新失败语义，按照路线图保持 `deep`。
