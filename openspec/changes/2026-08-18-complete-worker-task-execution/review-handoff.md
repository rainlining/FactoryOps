# Review Handoff

- Change：`2026-08-18-complete-worker-task-execution`，`standard`
- 分支：`codex/complete-worker-task-execution`
- worktree：`C:\Users\小霖\Desktop\work\project2\FactoryOps\.worktrees\complete-worker-task-execution`
- stacked base：`cc247e0c4d2cce0021d12dd376c167309513673f`
- upstream merge：`d932041`（吸收 start provenance 修复与 handoff）
- 状态：`review-handoff-ready`

## 范围与调用链

migration 008 建立 completion request 幂等事实。入口 `WorkerTaskExecutionService.complete`：Contract 写前校验 → request 查重 → Task 锁 → request 并发重查 → lease 锁 → Execution 锁 → current RUNNING pair 校验 → Execution snapshot/history → Task snapshot/history → 条件删除 lease → request fact → commit。

成功只写 result 并将双方置 SUCCEEDED；不可重试失败只写 failure 并将双方置 FAILED。retryable failure 明确拒绝，等待独立 retry policy Change。失败或竞态导致整个事务回滚，lease 仅在所有状态/history 成功后删除。

## Review 路线

按 proposal/design → migration 008 → `CompleteWorkerExecutionCommand` → `_validate_completion` → `complete` 锁顺序 → `_finish_execution` → `_finish_task` → completion tests 阅读。最终 stacked 验证：completion 5、Agent 132、Contract 99、Java 65、Ruff/diff 全绿。

Standard Review 需实际检查成功或失败路径的双方 revision 2、history 与 lease 删除，并解释为何 retryable failure 不在本 Change。非目标包括自动 retry、新 attempt、LLM/Tool、heartbeat、Checkpoint、Java API、Evaluation 和 `dataset/`。Review 期间禁止并发修改本 worktree；验收前不得归档或合并 main。
