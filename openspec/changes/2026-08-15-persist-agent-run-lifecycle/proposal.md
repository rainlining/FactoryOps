# Change 提案：2026-08-15-persist-agent-run-lifecycle

## 元数据

- `change_id`: `2026-08-15-persist-agent-run-lifecycle`
- `status`: `review-handoff-ready`
- `learning_level`: `deep`
- `depends_on`: `[2026-08-15-define-agent-run-contract, 2026-08-15-consume-quality-incident-events-idempotently]`
- `spec_refs`: `[agent-run-contract, quality-incident-event-ingress]`
- `feature_branch`: `codex/persist-agent-run-lifecycle`

## 为什么要做

Workflow Run Contract 已冻结，Agent Service 也能将业务事件可靠写入 Inbox，但系统还不能持久化 Run、审计状态变化或抵御并发覆盖。若直接启动 Coordinator，进程重启后将无法判断 Run 是否创建、运行到哪个 revision，以及某次状态变化是否已提交。

本 Change 建立 Run 当前快照与 append-only transition 历史，并用 MySQL 事务、唯一约束和乐观锁冻结生命周期可靠性语义。

## 范围

- 新增 `agent_runs` 和 `agent_run_transitions` MySQL Schema、索引、外键和 `CHECK`。
- 将 migration runner 从单版本升级为有序多版本执行。
- 实现 original/replay 创建、读取和状态迁移的内部 Application Service。
- 实现创建幂等、transition request 幂等、乐观锁和冲突分类。
- 在同一事务更新当前快照并追加迁移历史。
- 修正 `PENDING → CANCELLED` 与 Agent Run Contract 的 `started_at` 矛盾。
- 提供领域单元测试、MySQL 8.4 集成测试和失败路径证据。

## 非目标

- Kafka Consumer 自动创建 Run。
- HTTP API、Coordinator、Agent Runtime、Agent Execution 或 Task。
- Checkpoint 实体、Resume 或 Replay 执行。
- progress 或 coordinator reference 更新入口。
- Redis 锁、分布式 Lease、删除或数据保留策略。

## 学习等级

`deep`。这是 Agent World 第一次实现 MySQL Schema/Index/Transaction、append-only audit、条件更新乐观锁以及写入失败后的新事务分类，包含新的事务、并发和失败模型。

## 验收摘要

- Run 与初始历史原子创建，快照更新与 transition 追加原子提交。
- 重复创建、重复迁移、冲突请求和过期 revision 可明确区分。
- identity/provenance 不会被状态迁移 SQL 修改。
- 独立 Review/Learning 会话完成两条真实事务调用链、Owner 修改和故障实验前，不得归档或合并 `main`。
