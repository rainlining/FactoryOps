# Review Handoff

- Change：`2026-08-18-retry-worker-task-execution`，`deep`
- 分支：`codex/retry-worker-task-execution`
- worktree：`C:\Users\小霖\Desktop\work\project2\FactoryOps\.worktrees\retry-worker-task-execution`
- base：`d6011370e7e8f5b722ec7b5e7200049766277741`
- implementation commit：`8ee70ee`
- 状态：`review-handoff-ready`

## 范围与调用链

migration 009 建立 retry request 幂等事实。入口 `WorkerTaskExecutionService.retry`：Contract/安全错误码校验 → request-key advisory lock → request 查重 → Task/lease/current Execution 行锁 → ownership、attempt budget 校验 → 旧 Execution FAILED/retryable + history → 新建 attempt+1 RUNNING Execution + histories → Task RUNNING→RUNNING、revision+1/current Execution 切换 + history → request fact → commit；lease 始终保留。

任一 history 或 SQL 失败整体回滚。相同 request 并发由 advisory lock 稳定分类 identical/conflicting。独立审查修复了既有 Completion 的 Task revision `1→2` 硬编码；现在 Completion 从锁定 snapshot 做 `n→n+1`，真实 MySQL 证明 attempt 2 可完成为 Task SUCCEEDED revision 3。

## Review 路线

按 proposal/design → migration 009 → `RetryWorkerExecutionCommand` → `_validate_retry` → `retry` 锁顺序 → `_fail_retryable_execution` → `_insert_running_execution` → `_retry_task` → retry MySQL tests 阅读。重点检查旧 Execution 不可变终态、新 Execution provenance、Task 不写 failure、lease 保留、预算拒绝和注入回滚。

验证：实现移交时 retry `7 passed`，相关组合 `45 passed`，Agent 全量 `143 passed`，Contract `99 passed`，Java `65 tests`。Review Owner 修改后 retry `8 passed`，单独 failure exercise `1 passed`；Ruff/diff/dataset 检查通过。非目标为自动循环/backoff、跨 worker 接管、heartbeat、LLM/Tool 调用或业务副作用重试、Checkpoint/Resume、Java API、Evaluation、`dataset/`。

Owner 修改：在安全错误 allowlist 中增加一个明确的测试错误码并补接受/拒绝测试。Failure exercise：注入新 Execution history 失败，确认旧 Execution/Task 仍 RUNNING、lease 保留且无 retry fact。Review 期间禁止并发修改本 worktree；Learning Gate 前不得归档或合并 main。

Review 结果：Owner 修改由 Codex 代做，新增 `WORKER_SANDBOX_UNAVAILABLE` 和真实 MySQL 接受测试；`INVALID_INPUT` 仍由负向测试拒绝。Failure exercise 已实际完成。由于 Owner 修改不是项目所有者亲自完成，Deep Learning Gate 不因本记录自动通过。
