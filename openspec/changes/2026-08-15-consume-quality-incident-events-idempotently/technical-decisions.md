# 技术选型与取舍

## 1. Consumer 所属：Python Agent Service

选择：在 `services/agent-service` 建立最小 Event Ingress。

放弃：Java 消费后再转发 Python；它会让 Business World 同时生产并消费 Agent 入口事件。也不在本 Change 创建完整 Agent Runtime，避免把 Kafka 可靠性与 LLM Workflow 混合。

## 2. Kafka Client：confluent-kafka

选择：使用基于 librdkafka 的 `confluent-kafka`，显式 poll、同步 commit、seek 和 Group metadata 行为成熟，适合学习真实 Consumer offset。

放弃：`aiokafka`。当前处理链是串行数据库事务，不需要为了异步框架增加 event loop、取消传播和并发语义。未来 Agent Runtime 采用 asyncio 时可在不改变 Processor/Repository Contract 的前提下替换 Worker adapter。

## 3. 幂等存储：MySQL Durable Inbox

选择：Agent 自有 MySQL Inbox，以 `event_id` 主键和 canonical hash 判断 new/identical/conflicting。

放弃 Redis SETNX。Redis 适合短期抑制和 Lease，但这里的幂等事实必须跨进程重启并与未来 Run 创建形成事务边界；Redis 持久化和过期策略会引入不必要的不确定性。Redis 幂等/Lock 保留为独立 Deep Change。

## 4. 数据库访问：SQLAlchemy Core + 显式 SQL migration

选择：SQLAlchemy Core 管理连接和事务，保留清晰 SQL；migration 使用版本化 SQL 文件和轻量 runner，不引入 ORM Entity 生命周期。

放弃完整 ORM/Alembic 脚手架。本 Change 只有两张入口可靠性表，重点是事务和 offset；后续 Agent Runtime 表模型扩大时再独立引入 Alembic，避免当前 Change 同时教授两套复杂机制。

## 5. Offset 策略：逐条同步 commit

选择：关闭 `enable.auto.commit` 与 `enable.auto.offset.store`；每条持久化后同步提交 `offset + 1`。

放弃批量异步 commit。批量会引入同一 Partition 中部分成功、失败洞和更高 offset 覆盖问题；当前吞吐不是主要目标。

## 6. 失败恢复：失败即 seek 当前 record

选择：数据库或 commit 失败时 seek 回当前 offset，禁止同一实例继续并最终提交更高 offset。

关键原因：`poll()` 会推进 Consumer 的本地 position，即使没有 commit。仅仅“不 commit”不能保证当前进程立即重试；若继续处理并提交后续 offset，失败消息会被逻辑跳过。

## 7. Poison Message：持久化隔离后提交

选择：非法或冲突消息写 rejection evidence 后提交 offset。证据只保存来源坐标、reason、event ID（可得时）和 payload hash，不保存原始非法载荷。

放弃无限重试，因为确定性非法消息重试不会变好，会阻塞 Partition。暂不增加 DLQ Topic，避免在同一 Change 发明新的事件 Contract 和 Producer 路径。

## 8. 原始与规范化内容

有效 Inbox 同时保存原始 Kafka bytes 和 canonical SHA-256。原始 bytes 用于 provenance/replay，canonical hash 用于忽略 JSON 空白与 key 顺序的语义幂等判断。

非法消息不保存原文，降低 ground truth 或未知敏感字段进入 Agent 数据面的风险。
