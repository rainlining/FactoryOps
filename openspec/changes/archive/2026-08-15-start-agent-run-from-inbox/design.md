# Change 设计：2026-08-15-start-agent-run-from-inbox

## 决策

采用同步 Consumer 编排：Inbox 事务完成后调用独立 `IncidentRunStarter`，Run 完成后才由 Worker 提交 offset。不采用跨 Repository 单事务或独立 Inbox Poller。

## 组件

- `AgentRuntimeConfig`：启动时加载并验证不可变版本清单。
- `DecodedEvent.incident_id`：显式业务字段，避免重解析 raw payload 或滥用 Kafka key。
- `IncidentRunStarter`：组装 Provenance并确保 event → original Run。
- `EventIngressProcessor`：路由 Inbox outcome 并调用 Starter。
- `KafkaIngressWorker/main`：保留 Kafka ownership，区分 retryable 与 fatal 异常。

## 数据流与事务

```text
decode
→ Inbox transaction commit
→ Run snapshot + initial history transaction commit
→ Kafka synchronous offset commit
```

两个数据库事务之间允许短暂间隙，但 offset 保持未提交。重投由 Inbox 幂等吸收，Run 由 `trigger_event_id` 唯一约束吸收。

## 状态与不变量

- 本 Change 只创建 `PENDING` Run。
- offset 已提交的可信事件必须已有唯一 original Run。
- 已有 Run 的 Provenance 永不随当前配置变化。
- rejected 事件不得产生 Run。
- 不增加 Inbox processing status，完成事实由 Inbox 与 Run 的关联表示。

## 失败路径

- Inbox 失败：无 Run、无 offset commit，seek 重试。
- Inbox 成功而 Run 失败：Inbox 可保留，无 offset commit，重投恢复。
- Run 成功而 offset commit 失败：重投返回 already-started。
- Incident 不一致或 Run Contract 损坏：fatal integrity error，不提交 offset。
- 配置非法：Kafka Consumer 创建前启动失败。

## 测试策略

使用单元测试验证路由和配置，MySQL 8.4 验证顺序事务、并发和故障恢复，Kafka+MySQL 端到端测试验证 offset 完成不变量。现有 Docker 基线需在实现前恢复。

## 放弃方案

- 单事务 Inbox+Run：需要扩大事务所有权重构。
- 独立 Poller：需要 processing status、Lease 和卡死恢复。
- Event 携带 Agent 配置：违反 Business/Agent 所有权。
- 运行时 Git 查询：容器不一定包含 `.git`。
