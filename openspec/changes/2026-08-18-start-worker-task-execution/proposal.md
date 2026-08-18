# Change 提案：启动 Worker Task Execution

- `change_id`: `2026-08-18-start-worker-task-execution`
- `status`: `applying`
- `learning_level`: `deep`
- `depends_on`: `2026-08-17-claim-agent-task-lease`
- `feature_branch`: `codex/start-worker-task-execution`

## 动机与范围

Task lease 已冻结短期 ownership，但 claim 后仍没有原子方式创建 Specialist Execution 并推进 Task。此 Change 让持有有效 lease 的 Worker 在一个 MySQL 事务内校验依赖、创建并启动 Execution、推进 Task `PENDING → RUNNING`，并保存请求幂等事实。

## 非目标

不执行 LLM/Tool，不完成 Task，不自动 retry，不实现 heartbeat/cleanup、Checkpoint/Resume、Java Business API、并行调度、Evaluation，也不修改 `dataset/`。

## 学习等级

`deep`。这是首次把 lease ownership、Task 和 Execution 放进同一事务，并新增过期 fencing、依赖 readiness 与跨聚合原子启动失败模型。
