# Review Handoff

## 恢复信息

- Change：`2026-08-20-define-human-approval-contract`
- 学习等级：`deep`，Owner Review/Learning 延后
- 分支/worktree：`codex/define-human-approval-contract` / `C:\Users\小霖\Desktop\work\project2\FactoryOps\.worktrees\define-human-approval-contract`
- stacked base：`f97cb63d281535585b42349aa8c3779764ea6585`
- 实现提交：`98134c5`；审查修复：`2f0d35e`；最终文档 HEAD 以本文件所在提交为准
- 远端：上游与当前分支因 GitHub 443 超时待补推

## 实现与调用链

新增 Human Approval v1 strict Schema、valid pending fixture、公开 validator、确定性 key/ID、canonical bytes 与 relation classifier。入口为 `validate_human_approval(payload, risk_decision)`：payload schema/preflight → Risk Decision canonical validation → Fusion subject/REQUIRE_APPROVAL 检查 → decision/fusion/run 与 Gate provenance 逐字段 binding → 时间/actor 不变量。

状态只允许 revision 1 PENDING 到 revision 2 APPROVED/REJECTED/EXPIRED。HUMAN 决定严格早于 expiry；从 expiry 瞬间起只允许 SYSTEM EXPIRED。APPROVED 仅代表人工 Gate 通过，不代表 Java 业务动作已执行。

非目标：不持久化、不提供 API/UI、不推进 Run/Execution、不发送 Kafka、不执行 Business Action、不修改 `dataset/`。

## 审查、验证与后续

首审 2 个 Important 已在 `2f0d35e` 修复，同一 Agent 复审为 0 Critical、0 Important。真实命令与结果见 `verification.md`。建议阅读顺序：proposal/spec/design → schema → `validate_human_approval` → `_validate_payload` → `_is_next` → tests。

下一个 Change 为 Approval Persistence；必须使用 Risk Decision FK/完整性读取、双 identity admission、revision 乐观并发和真实 MySQL 测试。Owner walkthrough/Learning Gate 延后，本 Change 不归档、不合并 main。
