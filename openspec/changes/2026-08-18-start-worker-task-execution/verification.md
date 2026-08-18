# Verification

- `python -m pytest -q tests/test_worker_task_execution_mysql.py`：`4 passed`。
- migration/Execution/Run/Task 相关真实 MySQL：`43 passed`。
- Agent Service 全量：`127 passed in 218.99s`。
- Contract：`99 passed`。
- Java `mvn verify -q`：exit 0，20 份 XML，`65 tests, 0 failures/errors/skipped`。
- `python -m ruff check .` 与 `python -m ruff format --check .`：通过。
- `git diff --check`：通过；diff 不含 `dataset/`。

局部证据：成功后 Task/Execution 均为 RUNNING revision 1，Execution 有 PENDING/RUNNING 两条 history；identical/conflicting replay 不增加 Execution；无效/过期 lease 与未完成依赖拒绝；注入 history 失败后 Task=PENDING 且 Execution/request 均为 0 行。

独立审查发现并修复两个 Important：并发 replay 在等待 Task 锁后重新读取 request fact；直接 SQL 路径对 provenance 执行 Contract 写前校验。无未处理 Critical/Important。
