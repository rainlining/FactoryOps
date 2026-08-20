# Review Handoff

- Change：`2026-08-21-resume-approved-action-execution`
- 学习等级：`deep`
- 分支：`codex/resume-approved-action-execution`
- worktree：`.worktrees/resume-approved-action-execution`
- stacked base：`766ccc6c053011f3bc3be80e99a7e39eca17f298`
- implementation HEAD：`3a470589800338f9b7754a69c30c462358633afe`
- 状态：`technically-verified`，等待独立审查。

## 调用链

`ApprovedActionResumeService.resume` → 无副作用 scope precheck → `HumanApprovalService.save(terminal)` → Agent transaction 依序锁 Fusion provenance / Risk / Run / Approval current+history / transition chain → `BusinessActionHttpClient.execute` → shared Schema + strict identity receipt validation → Run CAS + resume transition insert → commit → Approval wait-to-current chain re-read。

## 核心不变量

- 只有 APPROVED v1.1 HOLD_BATCH 与完全匹配 EXECUTED receipt 可恢复。
- 外调 Java 时持有 Run row fence；HTTP timeout 有界，不做单次无条件 retry。
- Java receipt 与 Agent resume transition 分别提供跨库 saga 的两个幂等锚点。
- Java 已执行/Agent rollback 后，相同调用通过 Java replay 恢复，只写一条 resume transition。
- Agent 已存在 resume fact 时，Java receipt 必须明确 `replayed=true`；否则按跨库完整性错误拒绝。
- HTTP 只连接冻结 origin、拒绝 redirect，service token 不跨 origin 转发。

验证与限制见 `verification.md`；学习任务见 `learning.md`。

禁止其他会话并发修改本 worktree。
