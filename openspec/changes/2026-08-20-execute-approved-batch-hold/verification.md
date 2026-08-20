# Verification

状态：`review-handoff-ready`。

## 实际验证

- 首轮 `mvn -q -Dtest=HumanApprovalHttpIT test`：`17 tests / 0 failures / 0 errors`。
- 审查回归 RED：receipt `approval_id` 漂移后旧实现泄漏 `DuplicateKeyException`；修复后局部真实 MySQL 为 `20 tests / 0 failures / 0 errors`。
- 修复后 `mvn verify -q`：退出码 0；递归 Surefire/Failsafe XML 为 `22 reports / 105 tests / 0 failures / 0 errors / 0 skipped`（HumanApprovalHttpIT 在两个报告目录各出现一次，按既有项目统计口径保留）。
- 修复后 `python -m pytest -q contracts`：`154 passed in 2.19s`。
- 修复后 `python -m pytest -q services/agent-service/tests`：`218 passed in 490.71s`。
- `git diff --check` 通过；`git status --short -- dataset` 无输出。
- 全仓 Ruff 存在上游既有 import/format findings；本 Change 没有 Python diff，未顺带修改。

## 真实证据

- APPROVED HOLD_BATCH 从 incident 解析 `BATCH-APPROVAL`，即使 body 注入 `ATTACKER-BATCH` 仍只冻结真实 Batch。
- 并发相同执行得到 applied+replay，receipt 只有一条。
- PENDING 与 APPROVED STOP_LINE 均零副作用拒绝。
- 注入 receipt CHECK failure 后，Batch hold 与 receipt 同事务回滚，Batch 仍 OPEN。
- replay 同时校验 receipt 与 Batch typed state，漂移时 fail closed。
- receipt ID/Key split 返回 `action_execution_integrity_error`，不新增第二条 receipt；Approval projection corruption 与冲突 Batch 均零副作用拒绝。

## 独立审查

首审：0 Critical、2 Important。Important 分别为 receipt 仅按 ID 查询导致 identity split 由唯一键异常决胜，以及 OpenSpec 的 `QUALITY_ANOMALY`/测试覆盖声明与实现不一致。修复采用 ID-or-Key 锁定与完整 identity 比对，明确人工批准执行使用 `MANUAL_QUALITY_HOLD`，并补三条真实 MySQL 回归。复审实际运行 HumanApprovalHttpIT 20 tests，结论 0 Critical、0 Important。

## 限制

V1 只执行 `HOLD_BATCH`；`STOP_LINE` 与 `REJECT_ITEM` 明确返回 unsupported，不在本 Change 静默建模。
