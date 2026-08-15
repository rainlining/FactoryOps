# Change 提案：2026-08-15-define-agent-run-contract

## 元数据

- `change_id`: `2026-08-15-define-agent-run-contract`
- `status`: `review-handoff-ready`
- `learning_level`: `deep`
- `depends_on`: `[2026-08-15-consume-quality-incident-events-idempotently]`
- `spec_refs`: `[quality-incident-event-ingress, development-governance]`
- `feature_branch`: `codex/define-agent-run-contract`

## 为什么要做

Agent Service 已能可靠接收 `quality.incident.opened`，但还没有一个稳定对象表达“一次质量问题的完整多 Agent 处理流程”。如果直接实现数据库、Coordinator 或 Checkpoint，各模块会分别发明 Run 的身份、状态、重放与来源语义，最终无法可靠恢复、审计和评测。

本 Change 先冻结 Workflow Run 的版本化 Contract，使后续持久化和运行时实现共享同一组不变量。

## 范围

- 定义 Workflow Run v1.0.0 的严格 JSON Schema。
- 区分 original Run 与 replay Run，并冻结身份和幂等键语义。
- 定义不可变 identity、不可变 provenance、可演进 lifecycle、执行引用和进度摘要。
- 冻结 Run 状态含义、终态分类和时间字段组合。
- 提供有效/无效 fixtures、Contract Validator、关系分类和自动化测试。
- 记录中文技术取舍、学习任务、故障实验和 Review Handoff。

## 非目标

- MySQL 表、Repository、事务、乐观锁或状态迁移服务。
- Kafka Consumer 到 Run 创建的连接。
- Coordinator、Agent Runtime、Agent Execution 或 Agent Task Contract。
- Checkpoint、Resume、Replay 的执行机制。
- Prompt Registry、Model Adapter、Tool Runtime 或 Evaluation Harness。

## 学习等级

`deep`。这是项目第一次建立 Agent Workflow 的身份、状态、Replay 和 Decision Provenance 语义。虽然本 Change 不包含运行时或数据库代码，但这里的 Contract 将约束后续 Coordinator、Checkpoint/Resume/Replay 和 Evaluation，属于新的关键语义，不能按已有 JSON Schema 模式降级。

## 后续顺序

1. `persist-agent-run-lifecycle`：把已冻结语义映射为 MySQL 模型、事务和合法状态迁移。
2. `start-agent-run-from-inbox`：从幂等 Inbox 创建唯一 original Run。
3. `define-agent-task-contract`：定义 Run 内任务和 Agent Execution 边界。
4. 后续 Coordinator、Checkpoint/Resume、Replay 与 Evaluation Change 复用本 Contract。

## 验收摘要

- Schema、Validator、fixtures 和关系测试能够执行并覆盖成功及失败边界。
- 不引入 FactoryOps 业务运行时代码、数据库或 Kafka 修改。
- 独立 Review/Learning 会话完成真实调用链、所有者修改、故障实验和最终 diff 接受前，保持 `awaiting-learning-gate`，不得合并 `main`。
