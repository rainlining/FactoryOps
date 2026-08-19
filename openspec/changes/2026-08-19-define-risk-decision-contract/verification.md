# Verification

- stacked base：`67fc8160c78946ea4bcb53cdf9b17de2f2f9f5ee`（`codex/persist-specialist-recommendation`）。
- 实现提交：`5514dc7`（`feat(contract): define risk decisions`）。
- RED/局部 Contract：首次实现 `5 passed`；独立审查修复后 `python -m pytest -q contracts/risk_decision/tests` → `8 passed`。
- 全 Contract：首次实现 `121 passed`；审查修复后 `python -m pytest -q contracts` → `124 passed`。
- Agent Service 全量：`python -m pytest -q services/agent-service/tests` → `152 passed`。
- Java：`mvn verify -q`（`backend/business-service`）退出码 0；Surefire/Failsafe `20` 份报告、`65` tests、`0` failures、`0` errors、`0` skipped。
- Ruff：`python -m ruff check contracts/risk_decision` 通过；`python -m ruff format --check contracts/risk_decision` 通过。
- Schema：`python -m json.tool contracts/risk_decision/v1.0.0/schema.json` 通过。
- `git diff --check` 通过；`dataset/` 无修改。

独立审查修复：补充 `decision` 与 `allowed_actions` 一致性，避免 BLOCK/REQUIRE_APPROVAL 同时声称 proposed action 已授权；新增 2 个负向断言。未发现 Critical/Important 遗留问题。

第二次独立子 Agent 审查发现 2 个 Important：跨 Recommendation identity 未真实比对；整数与等值整数浮点未 canonical 归一化。现已要求公开 validator 接收源 identity 并逐字段比对，同时增加数字归一化及 3 组 mismatch、1 组 relation 回归。子 Agent 对 `d924339` 复审通过，两个 Important 均关闭，0 Critical、0 Important。

审查修复后 Agent Service 全量再次执行：`152 passed`。Java 无代码变化，沿用本 Change 首次全量 `mvn verify -q` 的 65 tests 通过证据。

限制：当前仅冻结 Python Contract 与 validator，未实现 Risk Agent、持久化、Approval 或执行 API；Deep Learning Gate 尚未完成。
