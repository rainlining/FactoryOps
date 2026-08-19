# Verification

- stacked base：`f3bc9e9`（Risk Contract review-passed tree）。
- 局部真实 MySQL：`python -m pytest -q tests/test_risk_decision_mysql.py` → `7 passed`。
- 迁移相关回归：`12 passed`。
- Agent Service 全量：`python -m pytest -q` → `159 passed`。
- 全 Contract：`python -m pytest -q contracts` → `124 passed`。
- Java：本 Change 未修改 Java；此前同一 stacked base 的 `mvn verify -q` 为 `65 tests`、0 failures/errors/skipped。
- Ruff：Agent Service `python -m ruff check src tests` 与 `format --check` 通过。
- `git diff --check` 通过；`dataset/` 未修改。

实现提交：`aa49338`；迁移断言修复：`1888b0e`。

已知限制：Java 本 Change 无代码变化，未重复启动耗时较长的 Maven 套件；Risk Agent、Approval 和 Business Action 不在范围内。
