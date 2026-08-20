# Verification

状态：`technically-verified`，等待独立子 Agent 审查。

## 实际验证

- `mvn -q -Dtest=HumanApprovalHttpIT test`：`17 tests / 0 failures / 0 errors`。
- `mvn verify -q`：退出码 0；递归 Surefire/Failsafe XML 为 `22 reports / 99 tests / 0 failures / 0 errors / 0 skipped`（HumanApprovalHttpIT 在两个报告目录各出现一次，按既有项目统计口径保留）。
- `python -m pytest -q contracts`：`154 passed in 2.45s`。
- `python -m pytest -q services/agent-service/tests`：`218 passed in 512.41s`。
- `git diff --check` 通过；`git status --short -- dataset` 无输出。
- 全仓 Ruff 存在上游既有 import/format findings；本 Change 没有 Python diff，未顺带修改。

## 真实证据

- APPROVED HOLD_BATCH 从 incident 解析 `BATCH-APPROVAL`，即使 body 注入 `ATTACKER-BATCH` 仍只冻结真实 Batch。
- 并发相同执行得到 applied+replay，receipt 只有一条。
- PENDING 与 APPROVED STOP_LINE 均零副作用拒绝。
- 注入 receipt CHECK failure 后，Batch hold 与 receipt 同事务回滚，Batch 仍 OPEN。
- replay 同时校验 receipt 与 Batch typed state，漂移时 fail closed。

## 限制

V1 只执行 `HOLD_BATCH`；`STOP_LINE` 与 `REJECT_ITEM` 明确返回 unsupported，不在本 Change 静默建模。
