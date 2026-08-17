# Change 提案：Coordinator Dispatch Task

## 元数据

- `change_id`: `2026-08-17-dispatch-coordinator-task`
- `status`: `review-handoff-ready`
- `learning_level`: `standard`
- `depends_on`: `[2026-08-16-define-agent-task-contract, 2026-08-16-persist-agent-task-lifecycle, 2026-08-17-persist-agent-execution-lifecycle, 2026-08-17-start-coordinator-execution]`
- `stacked_base_commit`: `b8ff7eb01b4b51eca37d02db20a941dddf1e941e`
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

真实 MySQL 覆盖成功、同/冲突 request、非 Coordinator/非 RUNNING/跨 Run 拒绝、依赖校验和 history 回滚；全仓回归与独立审查通过后停在 review-handoff-ready。
