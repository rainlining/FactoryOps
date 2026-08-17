# Change 提案：Agent Task Lease

- `change_id`: `2026-08-17-claim-agent-task-lease`
- `status`: `review-handoff-ready`
- `learning_level`: `deep`
- `depends_on`: `[2026-08-17-dispatch-coordinator-task]`
- `stacked_base_commit`: `3df4c3dff05042e48f9892c1749a505fc48891c9`
- `feature_branch`: `codex/claim-agent-task-lease`

## 范围

新增短期 Task lease：owner、不可预测 token、expiry、claim/renew/release 和过期接管。Lease 独立于 Task 生命周期；claim 不自动创建 Execution 或推进 Task 状态。

## 非目标

Worker 执行、Task RUNNING、Execution 创建、自动 retry、Redis、并行调度、LLM/Tool、Checkpoint/Resume、Java API、Evaluation、`dataset/`。

学习等级为 `deep`：首次定义 Worker ownership、过期和安全释放不变量。
