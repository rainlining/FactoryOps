# Review Handoff

- Change：`2026-08-20-operate-human-approval`（deep，demo 路线 3/10）
- 状态：`review-handoff-ready`；Owner Review/Learning Gate 延后
- 分支/worktree：`codex/operate-human-approval` / `.worktrees/operate-human-approval`
- stacked base：`4f8b38d1aa3e2208b2c5ef7d0ac23dc459d06417`
- 实现 commits：`cb7b501`、`7022018`
- 已验证并首次推送内容 HEAD：`0626114e191679ae15312056462c698c0ec42284`；仅含本字段与 T6 状态的收尾 commit 以远端分支 HEAD 为准

## 范围与边界

Java Business Backend 新增 internal PENDING intake、public query、authenticated decision API，V6 `business_approvals` current 与 immutable history，以及 Human Approval v1.0.0 schema/semantic validator。Agent Runtime 的同名 workflow fact 表未改；审批不执行动作、不推进 Run、不发布事件。

## 真实调用链

1. `HumanApprovalController.create` → service-token constant-time check → `HumanApprovalContractValidator` → create transaction。
2. `INSERT ... ON DUPLICATE` + connection-local marker 解决缺失 PK 并发 admission；key/ID row lock 后分类 created/replay/conflict，current + history revision 1 同事务。
3. `HumanApprovalController.decide` → actor ID + independent secret token → row `FOR UPDATE` → expiry/terminal replay/conflict → CAS current + history revision 2。
4. `get` 重验 schema、derived identity、canonical hash、全部 typed projection、完整 revision history 与 current=latest history，损坏 fail closed。

## 验证与审查

局部 8/8；Java 全量 81/81；Contract 151/151；diff-check 与 dataset 检查通过。首审两个 Important 已修复，同一子 Agent 复审 0 Critical/Important。

建议阅读：V6 migration → `ApprovalSecurity` → `HumanApprovalContractValidator` → `HumanApprovalApplicationService` → controller/advice → `HumanApprovalHttpIT`。禁止在 Owner Review 前并发修改此 worktree。

Owner 小修改：增加不改变权限的可选审计 reference 并补 terminal replay。Failure exercise：并发 APPROVED/REJECTED，确认一个 200、一个 409、history 只有 revision 1/2。
