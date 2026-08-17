# Change 提案：Agent Task Lease

- `change_id`: `2026-08-17-claim-agent-task-lease`
- `status`: `review-handoff-ready`
- `learning_level`: `deep`
- `depends_on`: `[2026-08-17-dispatch-coordinator-task]`
- `stacked_base_commit`: `af23d07fa94355508378f3561fc505f08f18285c`
- `dispatch_upstream`: `af23d07fa94355508378f3561fc505f08f18285c`
- `upstream_integration_merge`: `e8f47ebef8e25ea46e5f090ae165d4fc4bca2252`
- `feature_branch`: `codex/claim-agent-task-lease`

## 范围

新增短期 Task lease：owner、不可预测 token、expiry、claim/renew/release 和过期接管。Lease 独立于 Task 生命周期；claim 不自动创建 Execution 或推进 Task 状态。

## 非目标

Worker 执行、Task RUNNING、Execution 创建、自动 retry、Redis、并行调度、LLM/Tool、Checkpoint/Resume、Java API、Evaluation、`dataset/`。

学习等级为 `deep`：首次定义 Worker ownership、过期和安全释放不变量。

## 上游恢复结论

已吸收最新 Dispatch `af23d07`，因此同时包含 Coordinator Start Review 更新与 Execution Persistence 完整性修复。migration 004 preflight 在 Execution 表建立前审计逻辑引用；migration 006 在完整 Task/Execution schema 后新增独立 lease 表，两者顺序和事务职责不冲突。Dispatch 保持 Task PENDING，正是 lease claim 的合法输入；无需改变 Contract 或 lease ownership/expiry 语义。
