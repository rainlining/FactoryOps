# Change 提案：2026-08-16-persist-agent-task-lifecycle

## 元数据

- `change_id`: `2026-08-16-persist-agent-task-lifecycle`
- `status`: `review-handoff-ready`
- `learning_level`: `standard`
- `first_deep_reference`: `2026-08-15-persist-agent-run-lifecycle`
- `depends_on`: `[2026-08-15-persist-agent-run-lifecycle, 2026-08-16-define-agent-task-contract]`
- `base_commit`: `b39970ffb81c4051e64ca1a32d46ed6a89247595`
- `base_branch`: `codex/define-agent-task-contract`
- `feature_branch`: `codex/persist-agent-task-lifecycle`

## 为什么要做

Agent Task Contract 已冻结工作单元、依赖、attempt 摘要和终态语义，但 Coordinator 仍无法在进程重启后恢复 Task，也无法可靠判断一次 dispatch 或状态变化是否已经提交。若直接实现 Worker，重复请求、并发完成和依赖错误会造成重复 Task、快照覆盖或缺失审计历史。

本 Change 为 Task 建立 MySQL 当前快照与 append-only transition history，并在 Application Service 中固定请求幂等、依赖校验、乐观锁和 Contract 重建边界。

## 范围

- 新增 `agent_tasks`、`agent_task_dependencies` 和 `agent_task_transitions`。
- 创建以 `task_request_id` 幂等，并在同一事务写入快照、依赖和初始历史。
- 依赖 Task 必须存在、属于同一 Run、不可自依赖或重复。
- transition 以 `transition_request_id` 幂等，并以 status + revision 乐观锁保护并发。
- 支持 PENDING、RUNNING（含 retry attempt）、SUCCEEDED、FAILED、CANCELLED、SKIPPED 的 Contract 合法迁移。
- snapshot 更新与 history 追加同事务；读取时重建并验证 Agent Task Contract。
- 提供领域单元测试、MySQL 8.4 集成测试、失败注入与并发验证。

## 非目标

- Agent Execution 持久化或 Execution 外键。
- Coordinator Worker、dispatch loop、Task claim/lease 或并行调度。
- retry policy、timeout、Checkpoint/Resume。
- LLM、Tool、Java Business API、审批和业务副作用。
- Evaluation 或 `dataset/`。

## 学习等级理由

`standard`。本 Change 复用首次 deep Change `2026-08-15-persist-agent-run-lifecycle` 的 MySQL snapshot + append-only history、同事务提交、请求幂等和 revision 乐观锁模式。相同点是事务边界、冲突分类和失败模型；新增点是 Task type/role、同 Run 依赖、attempt 摘要及 `SKIPPED`。这些新增点不引入新的 lease、分布式 ownership 或跨库事务，因此按重复模式递减为 standard。

## 阶段性限制

Task 的 `created_by_execution_id`、`current_execution_id`、completion/failure execution ID 会经过 Contract 校验，但当前没有 Agent Execution 表，故暂为逻辑引用。Execution 持久化建立后必须通过独立 migration 增加同库外键，不在本 Change 静默伪造引用完整性。

## 验收摘要

- 技术：创建、依赖、迁移、幂等、并发、原子性和 Contract 重建均有真实测试证据。
- 学习：与上游两个 Change 按 Execution Contract → Task Contract → Task Persistence 顺序在独立 Review/Learning 会话完成 review；每个 Change 独立通过自己的 Learning Gate。
