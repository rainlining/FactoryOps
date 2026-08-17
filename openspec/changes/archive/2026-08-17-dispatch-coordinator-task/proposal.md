# Change 提案：Coordinator Dispatch Task

## 元数据

- `change_id`: `2026-08-17-dispatch-coordinator-task`
- `status`: `completed`
- `learning_level`: `standard`
- `depends_on`: `[2026-08-16-define-agent-task-contract, 2026-08-16-persist-agent-task-lifecycle, 2026-08-17-persist-agent-execution-lifecycle, 2026-08-17-start-coordinator-execution]`
- `stacked_base_commit`: `70a1309afa8a562bca0ce27fa18d415b591191c0`
- `execution_persistence_upstream`: `49561e83739bc17a45c297043a11fae4bfc96305`
- `coordinator_start_upstream`: `70a1309afa8a562bca0ce27fa18d415b591191c0`
- `feature_branch`: `codex/dispatch-coordinator-task`

## 动机与范围

Coordinator 已能启动，但还不能把一个确定的专业工作单元持久化为 Task。直接调用通用 Task Service 无法在检查 Coordinator Execution 与写 Task 之间保持一致性。本 Change 增加单个 dispatch admission：锁定 RUNNING Coordinator，原子创建 PENDING Task、依赖 junction 和初始 history，并支持 `task_request_id` 重放。

## 非目标

- Task 置 RUNNING、Worker claim/lease、并行调度、自动 retry。
- LLM/Tool、依赖图全局环检测、Checkpoint/Resume。
- 多 Task 批量 dispatch、Decision/Approval、Java API、Evaluation、`dataset/`。

## 学习等级

`standard`。复用 Task snapshot/history、请求幂等和 FK 模式；新增点是 Coordinator Execution ownership admission 与 Execution/Task 同事务父锁，但不引入新的长期 ownership 或跨库事务。

## 验收

真实 MySQL 覆盖成功、相同 request、非 Coordinator/非 RUNNING/跨 Run 拒绝及依赖校验；全仓回归与独立审查通过。conflicting replay 和完整 history rollback 的真实覆盖仍作为归档 follow-up 保留。

## 上游 Review 恢复

2026-08-17 已通过 merge commit 吸收 Coordinator Start 最新 Review 树 `70a1309`；该树包含与 Execution Persistence `49561e8` 等价的完整性修复，以及 Coordinator Start Owner 测试和状态文档。完整性修复只加强 migration 004 preflight、Execution result/failure 数据库约束和持久化重建校验，不改变 dispatch 的 Task Contract 或事务不变量。
