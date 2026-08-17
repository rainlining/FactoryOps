# 技术验证

## 环境与 TDD 证据

- 分支：`codex/start-coordinator-execution`
- stacked base：`8e73eb57a269dc453c78152f84d6a547fd02f633`
- 持久化测试：Testcontainers MySQL 8.4。
- 首次 RED：`ModuleNotFoundError: factoryops_agent_service.coordinator_start`，测试收集失败。
- 首轮实现：`5 failed`，暴露测试 Run provenance/ID 不符合既有 Contract。
- 修正夹具后：`4 passed, 1 failed`，暴露测试读取了错误的 Run Contract 字段层级。
- Run/Execution/Start 局部回归：`30 passed in 58.17s`。
- 最终 Start 局部：`6 passed in 19.30s`。

## 最终命令与结果

| 命令 | 结果 |
|---|---|
| `python -m pytest contracts -q` | `99 passed in 0.93s` |
| `python -m pytest -q`（Agent Service） | `112 passed in 186.02s` |
| `python -m ruff check .` | `All checks passed` |
| `python -m ruff format --check .` | `48 files already formatted` |
| `mvn verify -q`（Business Service） | exit code 0；20 份 XML，`65 tests, 0 failures, 0 errors, 0 skipped` |
| `git diff --check` | 通过 |

Java 日志中的 broker unavailable、missing topic 和连接错误属于既有负向/恢复测试；以 Maven exit code 和 XML 汇总为准。

## 审查与可观察证据

独立审查发现 1 个 Important：若低层 Execution Service 已为 PENDING Run 创建相同 Coordinator execution key，启动用例会泄漏原始 `IntegrityError`。已改为查询竞争 Execution、返回稳定 `concurrency-conflict`，并增加真实 MySQL 回归；复审为 0 Critical / 0 Important。

- 成功后 Run 为 RUNNING revision 1，Coordinator Execution 为 PENDING revision 0，关联 ID 一致。
- Run/Execution history 分别为 2/1 条，start receipt 为 1 条。
- 同 Run 并发两个 request 只有一个 `applied`，只存在一个 Coordinator Execution。
- 注入 Run history 失败后，Run 仍 PENDING revision 0，Execution 与 receipt 均为 0。
- 相同 request 重放不增加 revision、history 或计数；不同 payload 返回 conflicting。

## 限制与状态

- 没有 Redis lease、心跳、Worker 长期 ownership 或 fencing token。
- 不执行模型、Tool 或 Task dispatch；Context 仍只是已冻结引用。
- 技术验证完成并停在 `review-handoff-ready`。这是 Deep Change，Owner 修改、故障实验和 Learning Gate 尚未完成，不得归档或合并 `main`。
