# Verification

- completion 真实 MySQL：`5 passed`；覆盖成功、不可重试失败、identical/conflicting replay、错误 owner、非法 result 和 history 全回滚。
- 最终 stacked Agent Service 全量：`132 passed in 236.23s`。
- Contract：`99 passed`。
- Java `mvn verify -q`：exit 0；20 份 XML，`65 tests, 0 failures/errors/skipped`。
- `python -m ruff check .`、`python -m ruff format --check .`：通过，57 files formatted。
- `git diff --check`：通过；diff 不含 `dataset/`。

数据库证据：成功后 Task/Execution 均为 SUCCEEDED revision 2 且 lease 删除；失败后双方为 FAILED、引用同一 Execution 和 non_retryable failure；注入 completion history 失败后双方仍 RUNNING、lease 保留且 completion request 为 0 行。

独立审查发现并修复 Important：直接 SQL 终态路径补齐 result/failure 的字段集合、长度、pattern、唯一引用和互斥写前校验，防止数据库 CHECK 接受但 JSON Contract 拒绝的数据。无未处理 Critical/Important。
