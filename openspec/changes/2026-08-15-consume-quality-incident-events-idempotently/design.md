# 设计：幂等消费 Quality Incident 事件

## 边界

新增 `services/agent-service`，当前只有 `event_ingress`。它依赖冻结的 Python Contract validator、Kafka 和 Agent 自有 MySQL 表。它不依赖 FastAPI，因为后台 Consumer 不需要 HTTP 才能运行；未来 Agent API 可在独立 Change 接入同一 service package。

## 组件

- `KafkaRecordDecoder`：UTF-8、JSON、Contract、routing key 校验并计算 canonical hash。
- `InboxRepository`：在一个数据库事务内执行首次插入、相同判断或隔离登记。
- `EventIngressProcessor`：组合 decoder 与 repository，返回确定性 outcome。
- `KafkaIngressWorker`：poll 一条、处理一条、同步提交一条；失败时 seek 当前 offset。
- SQL migration：建立 `agent_event_inbox` 与 `agent_event_rejections`，不修改业务表。

## 成功数据流

```text
Kafka poll(record)
→ decode + contract/routing validation
→ MySQL transaction
   → new: INSERT inbox
   → identical: read existing, no second insert
   → invalid/conflict: INSERT rejection evidence
→ COMMIT MySQL
→ synchronous commit(record.offset + 1)
→ structured log
```

## 事务与不变量

- `agent_event_inbox.event_id` 是主键，一个业务事件最多一条 Inbox。
- `(topic, partition, kafka_offset)` 唯一标识 Kafka 来源坐标。
- rejection 以 Kafka 来源坐标为主键，重试隔离本身也幂等。
- canonical hash 用冻结 validator 的 canonical bytes 计算；原始 bytes 另存以保留 provenance。
- offset 不是“最后处理的 offset”，而是“下一条要读取的 offset”，所以提交 `record.offset + 1`。

## 失败路径

- decode/contract/key 失败：写 rejection 后提交 offset，避免 poison loop。
- MySQL 失败：不提交 offset，seek 当前 record；同一进程不得越过它。
- MySQL commit 后进程崩溃：Kafka 重投，Inbox 判断 identical 后提交。
- offset commit 失败：seek 当前 record；重投由 Inbox 吸收。
- rebalance 导致 commit/seek 失败：不伪造成功，新 owner 从 broker committed offset 恢复。
- 同 event ID、不同有效内容：保存冲突 hash/reason，不覆盖历史 Inbox，然后提交该冲突 record。

## 测试策略

- 纯单元测试：decoder、outcome、worker commit/seek 顺序。
- MySQL 集成测试：首次插入、相同重投、冲突、rejection 幂等、事务回滚。
- Kafka + MySQL 端到端：关闭 auto commit，验证 DB 成功/offset 失败后的重投和最终 committed offset。
- Contract 回归：现有 35 个 Python Contract 测试继续通过。

## 明确限制

当前每次 poll 后串行处理一条，牺牲吞吐换取可解释的 Partition 顺序。多 Worker、批量 commit、pause/resume、退避和 DLQ 留给后续可靠性 Change。
