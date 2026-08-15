# Start Agent Run from Inbox 技术设计

## 目标

将已经可靠持久化的 `quality.incident.opened` Inbox 事实连接到唯一 original Workflow Run。只有 Inbox 处理与 Run 建立均完成后，Kafka Consumer 才提交当前 record 的 offset。

本设计不启动 Coordinator，不调用 LLM，也不把 Run 从 `PENDING` 推进到 `RUNNING`。

## 架构

```text
KafkaIngressWorker
  └─ EventIngressProcessor
       ├─ KafkaRecordDecoder
       ├─ MySqlInboxRepository
       └─ IncidentRunStarter
            └─ AgentRunLifecycleService
```

- Worker 只管理 poll、commit、seek 和进程边界日志。
- Processor 根据 Inbox outcome 决定是否确保 Run 存在。
- Starter 把可信事件的 Incident 与启动配置组合为 Run Provenance。
- Lifecycle Service 继续拥有 Run Contract、事务和底层严格幂等。

## 成功数据流

```text
Kafka record
→ Decode 一次并产生 DecodedEvent.incident_id
→ Inbox commit
→ ensure_original_run
→ Run snapshot + initial history commit
→ Kafka commit(offset + 1)
```

`accepted` 与 `duplicate-identical` 都必须调用 Starter。`rejected-invalid` 与 `rejected-conflicting` 不创建 Run，在 rejection 证据提交后可提交 offset。

## 完成不变量

```text
Kafka offset 已提交
⇒ record 已获得持久化处理结果
⇒ 若事件可信，则唯一 original Run 已存在
```

Inbox 和 Run 使用顺序事务，不追求跨表单事务。Inbox 成功而 Run 失败时不提交 offset；Kafka 重投先被 Inbox 幂等吸收，再补建或确认 Run。

## Ensure 语义与部署跨越

底层 `create_original_run` 比较完整创建命令；Starter 的 `ensure_original_run` 判断可信事件是否已有正确 Run：

- 没有 Run：使用当前 `AgentRuntimeConfig` 创建；
- 已有同一 `trigger_event_id` 且 Incident 一致：返回 `already-started`，沿用已冻结 Provenance；
- 已有 Run 的 Incident 不一致或无法通过 Contract 重建：完整性错误。

因此，旧版本服务创建 Run 后在 offset commit 前崩溃，新版本服务即使配置已变化，也不会覆盖原 Provenance或永久卡住 Partition。

## 配置

启动时一次性加载并校验：

- `FACTORYOPS_AGENT_RUNTIME_VERSION`
- `FACTORYOPS_AGENT_WORKFLOW_VERSION`
- `FACTORYOPS_AGENT_PROMPT_SET_VERSION`
- `FACTORYOPS_AGENT_MODEL_POLICY_VERSION`
- `FACTORYOPS_AGENT_TOOL_POLICY_VERSION`
- `FACTORYOPS_AGENT_CONTEXT_POLICY_VERSION`
- `FACTORYOPS_AGENT_CODE_REVISION`

任一配置缺失或格式非法时，在创建 Kafka Consumer 前终止启动。不在运行时调用 Git，也不使用 `latest` 默认值。

## 失败分类

可重试：临时数据库错误、死锁、连接失败、Kafka commit 失败。Worker 不提交 offset，seek 当前 record，主循环等待后重试。

不可重试：Run 与事件 Incident 不一致、持久化 Run 违反 Contract、启动配置非法。系统不提交 offset，并让进程退出等待人工修复。

## 结果与日志

`ProcessingResult` 增加 `run_id` 和 `run_start_outcome`：`created`、`already-started`、`not-applicable`。

日志包含 topic、partition、offset、event ID、ingress outcome、run ID、run start outcome、耗时、commit 结果和 redelivery；不记录完整 payload、Prompt 或 Context。

## 验证

- 单元测试覆盖 Decoder、Processor 路由、配置和异常分类。
- MySQL 测试覆盖补建、已存在、配置变化、并发唯一赢家、Incident 冲突和事务失败。
- Kafka+MySQL 端到端测试覆盖 record → Inbox → PENDING Run → offset commit。
- 故障实验在 Inbox commit 后、Run 创建前注入一次失败，证明重投后恢复。

## 非目标

Coordinator、RUNNING 迁移、Agent Task/Execution、LLM、Tool、Poller、Lease、Redis Lock、Checkpoint/Resume/Replay、DLQ、Metrics/Trace SDK 和新 Inbox 状态字段均不在本 Change。
