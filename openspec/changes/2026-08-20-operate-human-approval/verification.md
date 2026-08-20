# Verification

状态：`review-handoff-ready`。

## TDD 与实际验证

- RED：首次 `mvn -q -Dtest=HumanApprovalHttpIT test` 因 V6 表不存在产生 6 errors；第一版 GREEN 又实际暴露 snake_case DTO、duplicate affected-row 与 expiry 分类问题，均修复后重跑。
- 局部真实 MySQL/HTTP：`mvn -q -Dtest=HumanApprovalHttpIT test` → 8 tests、0 failures/errors/skipped；独立复审同样实跑 8/8。
- Java 全量：`mvn verify -q` → exit 0；XML 汇总 22 reports、81 tests、0 failures、0 errors、0 skipped。
- Contract 全量：`python -m pytest -q contracts` → `151 passed in 2.57s`。
- `git diff --check` 通过；`git status --short -- dataset` 无输出。

## 独立审查

首审：0 Critical、2 Important、1 Minor。Important 为 actor ID 可冒充、current 时间/终态审计 projection 未完整比对；均已修复并增加 wrong-token 与 audit corruption 真实 MySQL 回归。Minor 经核对撤销：既有全局 `InspectionExceptionHandler` 已稳定映射 malformed JSON。复审：0 Critical、0 Important。

## 限制

本地 demo 使用服务端静态 actor credential allowlist，不等同企业 SSO/RBAC。审批结果尚不发布事件、不推进 Agent Workflow、不执行业务动作；这些属于后续 Change。Owner Review/Learning Gate 延后，因此不归档、不合并 main。
