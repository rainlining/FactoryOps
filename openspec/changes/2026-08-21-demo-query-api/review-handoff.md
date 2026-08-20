# Review Handoff

- Change：`2026-08-21-demo-query-api`
- 分支：`codex/demo-query-api`
- worktree：`.worktrees/demo-query-api`
- stacked base：`3be0b668`
- 状态：`review-handoff-ready`
- 最终本地 HEAD：待提交
- 独立复审：0 Critical / 0 Important。
- 真实入口：`factoryops_agent_service.demo_query.WorkflowSnapshotQueryService.get(run_id)`；只读 Agent DB，按 Run 验证 Coordinator→Fusion→Risk→Approval provenance。
- 已知限制：Business Receipt 位于 Java DB，本 Change 不跨库读取；真实 MySQL fixture 将由后续 demo 场景 Change 提供。

实现会话完成后停在 `review-handoff-ready`，不得归档或合并 main。
