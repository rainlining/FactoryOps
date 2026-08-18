# 设计

入口为 `WorkerTaskExecutionService.retry`。锁顺序固定为 request-key advisory lock → retry request → Task → lease → current Execution。校验 current RUNNING pair、lease fencing、安全错误码、retryable recoverability 和 attempt budget 后，在一个事务执行：旧 Execution RUNNING→FAILED revision 2/history；新 Execution 以 attempt+1 创建 RUNNING snapshot 和两条 history；Task RUNNING→RUNNING、revision+1、current Execution/attempt_count 更新并追加 history；写 retry request。lease 不删除。

request advisory lock 在事务外取得并在 finally 释放，解决缺失 request PK 无法跨不同 Task 串行化的问题。新 Execution provenance 由命令显式提供，旧 Execution 不被覆盖。任一写入失败全部回滚。

Task revision 不是固定值：每次 retry 做 `n → n+1`，后续 Completion 也必须从已锁定 Task 的当前 revision 做 `n → n+1`。否则 attempt 2 虽能启动却无法完成。

安全错误集合仅包含 `MODEL_TIMEOUT`、`TOOL_TIMEOUT`、`TRANSIENT_UPSTREAM`、`RATE_LIMITED`、`WORKER_SANDBOX_UNAVAILABLE`；它表示 attempt 可以重建，不表示自动重放已产生业务副作用的 Tool。`WORKER_SANDBOX_UNAVAILABLE` 表示 Worker 隔离运行环境分配失败，尚未开始业务 Tool 副作用。max attempts 为 2..10，且必须大于当前 attempt。
