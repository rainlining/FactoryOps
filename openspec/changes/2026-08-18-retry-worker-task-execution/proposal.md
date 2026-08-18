# Change 提案：重试 Worker Task Execution

- `change_id`: `2026-08-18-retry-worker-task-execution`
- `status`: `review-handoff-ready`
- `learning_level`: `deep`
- `depends_on`: `2026-08-18-complete-worker-task-execution`
- `feature_branch`: `codex/retry-worker-task-execution`

## 动机与范围

Worker 当前只能成功或不可重试失败；安全的瞬时技术故障无法保留失败 attempt 并创建下一 attempt。本 Change 在同一有效 lease 和 MySQL 事务中把当前 Execution 收口为 FAILED/retryable，创建并启动 attempt+1，并让 Task 保持 RUNNING、切换 current Execution。请求按 request ID 幂等，max attempts 和安全错误码由确定性规则检查。

## 非目标

不做自动循环、backoff、跨 worker 接管、heartbeat、timeout 检测、LLM/Tool 调用、业务副作用重试、Checkpoint/Resume、Java API、Evaluation，也不修改 `dataset/`。

## 学习等级

`deep`。复用 Start 的 lease fencing/request admission 与 Completion 的 Execution 收口，但首次引入 attempt replacement：旧 attempt 进入不可变终态、新 attempt 同事务进入 RUNNING、Task 保持 RUNNING 且 lease 保留。
