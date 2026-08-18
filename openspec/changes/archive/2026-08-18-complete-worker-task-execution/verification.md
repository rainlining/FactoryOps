# Verification

- completion 真实 MySQL：`7 passed in 13.96s`；覆盖成功、不可重试失败、顺序/并发 identical/conflicting replay、跨 Task request 竞争、错误 owner、非法 result 和 history 全回滚。
- 最终 stacked Agent Service 全量：`136 passed in 248.45s`。
- Contract：`99 passed`。
- Java `mvn verify -q`：exit 0；20 份 XML，`65 tests, 0 failures/errors/skipped`。
- `python -m ruff check .`、`python -m ruff format --check .`：通过，57 files formatted。
- `git diff --check`：通过；diff 不含 `dataset/`。

数据库证据：成功后 Task/Execution 均为 SUCCEEDED revision 2 且 lease 删除；失败后双方为 FAILED、引用同一 Execution 和 non_retryable failure；注入 completion history 失败后双方仍 RUNNING、lease 保留且 completion request 为 0 行。

首次独立审查修复了直接 SQL 终态 Contract 写前校验。Review 会话随后发现同型 Important：相同 completion request、不同 Task 并发可能在 request INSERT 泄漏主键冲突/deadlock。修复后以 request-key advisory lock 先行串行化；真实 MySQL 证明跨 Task得到 applied/conflicting 且输家双方 RUNNING/lease 保留，同 command 得到 applied/identical 且只有一份终态 history/fact。无未处理 Critical/Important。
