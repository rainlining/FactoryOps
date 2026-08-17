# 技术验证

## TDD 与审查

- 首次 RED：`ModuleNotFoundError: factoryops_agent_service.coordinator_task_dispatch`。
- 首轮实现暴露跨 Change 状态缺口：前一 Change 的 Run 为 RUNNING 但 Coordinator Execution 为 PENDING，dispatch 被错误拒绝。
- 修复为同事务将 PENDING Coordinator Execution 推进 RUNNING 后，局部 MySQL：`4 passed in 17.80s`。
- 独立审查发现 1 Important，已修复；复审 0 Critical / 0 Important。

## 上游 Review 同步验证

- 最新 Execution Persistence 远端 HEAD：`49561e83739bc17a45c297043a11fae4bfc96305`。
- 最新 Coordinator Start 远端 HEAD/新 stacked base：`70a1309afa8a562bca0ce27fa18d415b591191c0`。
- dispatch 通过 merge commit `7966fe3` 吸收 Coordinator Start 最新树；其中 Execution integrity 修复对应上游提交 `ee2ce17`。
- 检查结论：新的 migration 004 孤立引用 preflight、result/failure 完整性约束和 Coordinator Start Owner 测试均与 dispatch 兼容；无需改变冻结 Contract、事务边界或 Change 范围。

## 最终验证

| 命令 | 结果 |
|---|---|
| `python -m pytest tests/test_coordinator_task_dispatch_mysql.py -q` | `4 passed in 11.03s` |
| `python -m pytest contracts -q` | `99 passed in 0.74s` |
| `python -m pytest -q`（Agent Service） | `120 passed in 183.19s` |
| `python -m ruff check .` | 通过 |
| `python -m ruff format --check .` | `53 files already formatted` |
| `mvn verify -q`（Business Service） | exit code 0；20 份 XML，`65 tests, 0 failures, 0 errors, 0 skipped` |
| `git diff --check` | 通过 |
| `git diff --name-only 70a1309..HEAD` | 仅 dispatch OpenSpec、实现与测试；无 `dataset/` |

Java 日志中的 broker unavailable、missing topic 和连接错误属于既有负向/恢复测试，以 Maven exit code/XML 为准。

## 证据与限制

- 成功 dispatch：Coordinator Execution PENDING→RUNNING revision 1；Task 为 PENDING revision 0，created_by_execution_id 与 Coordinator 一致。
- Task、依赖和 history 同事务；注入 history 失败后 Task 行数为 0。
- 相同 request 返回 identical，不同 payload 返回 conflicting；非法 owner/Run 返回拒绝。
- 不包含 Worker claim/lease、并行调度、自动 retry、LLM/Tool、Checkpoint/Resume、Java API、Evaluation、`dataset/`。
- 技术状态为 `review-handoff-ready`，等待 Review/Learning 会话完成最终接受。
