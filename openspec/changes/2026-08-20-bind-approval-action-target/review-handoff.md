# Review Handoff

- Change：`2026-08-20-bind-approval-action-target`
- 学习等级：`deep`（Owner Learning Gate 延后）
- 分支：`codex/bind-approval-action-target`
- worktree：`.worktrees/bind-approval-action-target`
- stacked base：`4319d2b93df025139a5fd846acf6133cd6cf1bc6`
- pre-review HEAD：`6485af1`
- 首审修复 commit：`095ece8`
- reviewed implementation HEAD：`5d4195360c7cc26d89aeb44ded695cd196bf6c6f`
- 状态：`review-handoff-ready`；首审 2 Important 已修复，同一子 Agent 复审 0 Critical / 0 Important。

## 已实现范围

- Human Approval v1.1 identity 增加 `incident_id`，并以 source Run Contract 校验 run/incident 链。
- Agent migration 015、同事务 Run row lock、current/history Contract 与 typed-column 完整性校验；v1.0 legacy 可读。
- Java Flyway V7、双版本 schema reader、v1.1-only create、v1.0 legacy read 与 incident typed projection。
- Approval key/ID 仍只由 decision key 派生；incident 不是第二套 identity admission key。

## 真实调用链

1. Contract：`validate_human_approval` → source Risk → source Run → incident binding。
2. Agent：`HumanApprovalService.save` → Fusion provenance locks → Risk row → Run row → Approval row → current/history。
3. Java create：`HumanApprovalController.create` → `HumanApprovalApplicationService.create` → dual-version validator → v1.1 gate → current/history insert。
4. Java read：current payload/schema/hash → typed incident → history chain；v1.0 要求数据库 incident 为 null。

## 失败路径

- 错 Run/incident、缺 source Run、typed incident 漂移：fail closed，不产生新历史。
- v1.0 新建：422 `approval_incident_binding_required`；既有 v1.0 仍可读取。
- v1.1 指向不存在的 Business Incident：422 `approval_incident_not_found`，零写入。
- migration 015 若 ALTER 已提交但 schema history 未写：验证列形状后补 history；异常列形状拒绝静默继续。

验证详情见 `verification.md`。非目标为动作执行、Risk/Fusion 改版、自由 Batch/Line 参数及 `dataset/` 修改。

Owner walkthrough：先读 Contract validator/tests，再读 Agent migration/save/decode，最后读 Java validator/service/HTTP IT。小修改与故障实验见 `learning.md`。禁止其他会话并发修改本 worktree。
