# Change 提案：2026-08-15-start-agent-run-from-inbox

## 元数据

- `change_id`: `2026-08-15-start-agent-run-from-inbox`
- `status`: `design-reviewed`
- `learning_level`: `deep`
- `depends_on`: `[2026-08-15-consume-quality-incident-events-idempotently, 2026-08-15-persist-agent-run-lifecycle]`
- `feature_branch`: `codex/start-agent-run-from-inbox`

## 为什么要做

Agent Service 已能可靠保存 Kafka 事件，也能持久化 original Run，但两个能力尚未连接。当前可信 Incident 事件即使已进入 Inbox，也不会形成 Workflow Run，Coordinator 后续没有可靠的工作流入口。

## 范围

- 在当前同步 Kafka 处理链中确保可信事件拥有唯一 original Run。
- 由启动配置冻结 Run Provenance。
- `DecodedEvent` 显式传递 Incident ID。
- 只有 Inbox 与 Run 均完成后才提交 offset。
- 区分可重试适配器失败与不可重试完整性/配置失败。
- 提供结构化处理结果、日志与真实 Kafka/MySQL 恢复测试。

## 非目标

- Coordinator、LLM、Agent Execution、Task、Tool 或 Run `RUNNING` 迁移。
- Inbox Poller、处理状态、Lease、Redis Lock 或新数据库 migration。
- Checkpoint、Resume、Replay 执行、DLQ 或通用 Observability 平台。

## 学习等级

`deep`。Inbox 和 Run 内部模式已经学习过，但本 Change 首次建立 Kafka offset、两个顺序 MySQL 事务和 original Run 之间的端到端完成不变量，并引入新的崩溃与部署跨越恢复语义。

## 验收摘要

可信事件无论首次交付还是重投，都在 offset commit 前拥有唯一 `PENDING` original Run；非法/冲突消息不启动 Run；确定性完整性错误不得无限重试。
