# Change 提案：完成 Worker Task Execution

- `change_id`: `2026-08-18-complete-worker-task-execution`
- `status`: `applying`
- `learning_level`: `standard`
- `depends_on`: `2026-08-18-start-worker-task-execution`
- `feature_branch`: `codex/complete-worker-task-execution`

## 动机与范围

Worker Execution 启动后必须以同一 ownership 和事务边界收口 Execution 与 Task。此 Change 支持成功和不可重试失败，写入双方 history、保存请求幂等事实并仅在事务成功时释放 lease。

## 非目标

不处理 retryable failure/新 attempt，不自动执行 Agent/LLM/Tool，不做 heartbeat、Checkpoint/Resume、Coordinator fusion、Java API、Evaluation 或 `dataset/`。

## 学习等级

`standard`。复用首次 deep Change `2026-08-18-start-worker-task-execution` 的 lease fencing、固定锁顺序、请求指纹和跨 Task/Execution 单事务模式；新增点是终态 result/failure 互斥及 commit 后 lease 删除，没有新的 ownership 模型。
