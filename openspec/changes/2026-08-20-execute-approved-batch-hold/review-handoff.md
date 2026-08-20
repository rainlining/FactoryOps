# Review Handoff

- Change：`2026-08-20-execute-approved-batch-hold`
- 学习等级：`deep`（Owner Learning Gate 延后）
- 分支：`codex/execute-approved-batch-hold`
- worktree：`.worktrees/execute-approved-batch-hold`
- stacked base：`8580387727eb7df452039de8795c71d64ccb2f42`
- implementation HEAD：`c6e42a0f551239ee7212e48e9354773baf0814a3`
- 状态：`review-handoff-ready`；独立复审 0 Critical、0 Important。

## 调用链

`HumanApprovalController.execute` → service-token → `ApprovedBatchHoldExecutionService.execute` → Incident share lock → Approval current/history lock+decode → receipt lock → `BatchApplicationService.hold` → receipt insert → 单事务提交。

## 核心不变量

- API 没有 target 参数；Incident 是唯一目标根。
- 仅 revision 2 APPROVED HOLD_BATCH 可执行。
- Batch 与 receipt 同成同败；Approval row 串行化重放，receipt 按 approval ID-or-Key 锁定并完整比对。
- receipt 与最终 Batch state 在 replay 时双重完整性校验。

验证、限制见 `verification.md`；Owner 小修改与故障实验见 `learning.md`。禁止其他会话并发修改本 worktree。
