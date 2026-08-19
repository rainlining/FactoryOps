# Verification

- stacked base：`f3bc9e9`（Risk Contract review-passed tree）。
- 局部真实 MySQL：首次 `7 passed`；独立审查修复后 `python -m pytest -q tests/test_risk_decision_mysql.py` → `9 passed`。
- 迁移相关回归：`12 passed`。
- Agent Service 全量：首次 `159 passed`；审查修复后 `python -m pytest -q` → `161 passed`。
- 全 Contract：`python -m pytest -q contracts` → `124 passed`。
- Java：本 Change 未修改 Java；此前同一 stacked base 的 `mvn verify -q` 为 `65 tests`、0 failures/errors/skipped。
- Ruff：Agent Service `python -m ruff check src tests` 与 `format --check` 通过。
- `git diff --check` 通过；`dataset/` 未修改。

实现提交：`aa49338`；迁移断言修复：`1888b0e`；canonical integrity 修复：`80b501d`。

独立子 Agent 首审发现 1 个 Important：读取未验证 payload 仍为 canonical JSON；另有双 identity 交叉并发测试 Minor。`80b501d` 增加 canonical 字节等值校验、同步 hash 的非 canonical corruption 回归，以及同 ID/不同 key、同 key/不同 ID 的真实并发覆盖。子 Agent 复审确认 0 Critical、0 Important。

已知限制：Java 本 Change 无代码变化，未重复启动耗时较长的 Maven 套件；Risk Agent、Approval 和 Business Action 不在范围内。
