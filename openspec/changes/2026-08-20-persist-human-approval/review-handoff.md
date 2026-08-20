# Review Handoff

- Change：`2026-08-20-persist-human-approval`（deep，demo 路线 2/10）
- 状态：`review-handoff-ready`；Owner Review/Learning Gate 延后
- 分支：`codex/persist-human-approval`
- worktree：`.worktrees/persist-human-approval`
- stacked base：`631206318cc3da93a2ac57889c902649e3a67728`
- 实现 commits：`d1ce68c`、`39a8c14`、`b43e481`
- 最终 HEAD：待本 handoff 提交后填写

## 已实现范围

Migration 014 保存审批 current snapshot 与不可变 revision history；`HumanApprovalService.save/get_by_key` 绑定真实 REQUIRE_APPROVAL Risk Decision 与完整 Fusion provenance，支持首次 PENDING、相同重放、PENDING→单一终态、并发终态决胜、identity split 拒绝和损坏读取拒绝。非目标仍为 HTTP/UI、认证通知、Run 推进及业务动作。

## 真实调用链

1. `HumanApprovalService.save` canonicalize Contract，并取得排序后的 approval key/ID admission locks。
2. FUSION Risk 路径按 Fusion row → Coordinator Execution → 排序 Recommendation → link rows 锁定完整 provenance。
3. 锁定并重读 Risk Decision，再锁 Approval current row；Contract relation 决定 identical、next-revision 或 conflicting。
4. 首次写 current + history revision 1；终态用 revision CAS 更新 current + 插入 history revision 2；事务失败全部回滚。
5. `get_by_key` 重验 current/history hash、canonical、typed columns、Risk/Fusion binding、revision chain 和 current=latest history。

Migration 入口为 `event_ingress/migration.py` 的 014 dispatcher；current-only partial DDL 仅在结构完全吻合时恢复，history-only/异常结构 fail closed。

## 审查与验证

独立首审的两个 Important（跨服务锁序、partial migration 恢复）均已修复。复审 HEAD `39a8c14`：0 Critical、0 Important；后续 `b43e481` 仅同步既有 migration 版本断言。

局部 MySQL 10 passed；migration/lifecycle 39 passed；Agent Service 213 passed；Contract 151 passed；Java 65/65。Ruff、diff-check、dataset 检查通过。

建议阅读顺序：migration 014 → `migration.py` → `human_approval.py` → `test_human_approval_mysql.py` → persistence spec/design。该 worktree 在 Owner Review 前禁止并发修改。

Owner 小修改：增加一个不改变权限边界的 approval `reason_code` 并补 Contract/persistence 回归。Failure exercise：在 current/history 任一 canonical/hash 中注入漂移，确认读取 fail closed 且不改写历史。
