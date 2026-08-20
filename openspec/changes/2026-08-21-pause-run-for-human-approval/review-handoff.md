# Review Handoff

- Change：`2026-08-21-pause-run-for-human-approval`
- 学习等级：`deep`（Owner Learning Gate 延后）
- 分支：`codex/pause-run-for-human-approval`
- worktree：`.worktrees/pause-run-for-human-approval`
- stacked base：`81f82f2c5612cdfd13be836a1738b6a94e9a67f8`
- implementation HEAD：`df2fa4edc00c57a4e590d4e1d5658357ec06fa8c`
- 状态：`technically-verified`，等待独立审查。

## 调用链

`HumanApprovalService.save` → Fusion/Risk provenance locks → Run `FOR UPDATE` + Contract decode → Approval identity lock → Approval current/history insert → `_pause_run_for_approval` CAS → deterministic Run transition insert → 单事务 commit。

读取/重放：`get_by_key/save existing` → `_decode` → Approval hash/schema/typed/history → Run Contract → `_validate_wait_transition`。

## 核心不变量

- 首次 Approval 只接受 RUNNING Run，且 Approval 与 wait transition 同成同败。
- transition ID/request ID 均从 Approval ID 派生，reason message 绑定 Approval key。
- 读取和重放都验证确定性 wait fact、从 wait 到 current 的连续合法 transition chain，以及 current status/reason/updated_at；合法恢复不会使历史 Approval 失效。
- terminal Approval 不恢复 Run，不调用 Java，不产生业务副作用。

验证与限制见 `verification.md`；Owner 小修改与故障实验见 `learning.md`。

禁止其他会话并发修改本 worktree。
