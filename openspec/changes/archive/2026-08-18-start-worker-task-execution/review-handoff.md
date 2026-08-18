# Review Handoff

- Change：`2026-08-18-start-worker-task-execution`，`deep`
- 分支：`codex/start-worker-task-execution`
- worktree：`C:\Users\小霖\Desktop\work\project2\FactoryOps\.worktrees\start-worker-task-execution`
- base：`16f23958a96b53bc764b4fb5c6953499aa1b9e51`
- 状态：`review-handoff-ready`

## 范围与调用链

migration 007 建立 start request 幂等事实。入口 `worker_task_execution.py::WorkerTaskExecutionService.start`：写前 Contract 校验 → request-key advisory lock → request 查重 → Task 行锁 → lease 行锁 → dependency readiness → Execution snapshot/history → Task snapshot/history → request fact → commit → finally 释放 advisory lock。

失败链：空/非法 provenance、错误或过期 lease、非 PENDING Task、未完成依赖、并发条件失败均拒绝；任一 SQL/history 失败整体回滚。lease token 只进入 SHA-256 command fingerprint，不明文保存到 request 表。

修改范围只含 OpenSpec、migration 007、启动编排和相关测试；不含 Agent 执行、completion/retry、heartbeat、Checkpoint、Java API 或 `dataset/`。

## Review 路线

按 proposal/design → migration 007 → command/result → `start` advisory/行锁 → `_insert_running_execution` → `_start_task` → 并发 replay/rollback 测试阅读。Review Important 已修复：跨 Task 同 request 不再泄漏数据库异常。最新局部验证为 6 passed；全量结果见 verification。

最新真实验证：Start 局部 6、相关 MySQL 45、Agent 129、Contract 99、Java 65、Ruff/diff 全绿。

Owner 修改：把测试中的合法 `runtime-v1` 改为另一个非空版本并确认数据库原样持久化。Failure exercise：注入 Execution history 失败，确认 Task 保持 PENDING，Execution/request 不存在。完成 Deep Learning Gate 前不得归档或合并 main；Review 期间禁止并发修改该 worktree。

## 归档结果

项目所有者于 2026-08-18 确认可以归档；上述禁止归档文字是 handoff 阶段的历史约束。实现经 `9c15884` 合入 `main`，规格已归并到 `openspec/specs/worker-task-execution-start/`。
