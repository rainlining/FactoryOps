# Verification

- `python -m pytest -q tests/test_worker_task_execution_mysql.py`：`6 passed`。
- migration/Execution/Run/Task 相关真实 MySQL：`45 passed in 123.74s`。
- Agent Service 全量：`129 passed in 222.61s`。
- Contract：`99 passed`。
- Java `mvn verify -q`：exit 0，20 份 XML，`65 tests, 0 failures/errors/skipped`。
- `python -m ruff check .` 与 `python -m ruff format --check .`：通过。
- `git diff --check`：通过；diff 不含 `dataset/`。

局部证据：成功后 Task/Execution 均为 RUNNING revision 1，Execution 有 PENDING/RUNNING 两条 history；identical/conflicting replay 不增加 Execution；无效/过期 lease 与未完成依赖拒绝；注入 history 失败后 Task=PENDING 且 Execution/request 均为 0 行。

首次独立审查修复了 provenance Contract 写前校验。Review 会话随后发现 Important：相同 request、不同 Task 并发会锁不同 Task，可能在 request INSERT 泄漏 duplicate key/deadlock。修复后以 request-key advisory lock 先行串行化；真实 MySQL 回归证明跨 Task 得到 applied/conflicting、同 command 得到 applied/identical，输家无 Execution。无未处理 Critical/Important。
