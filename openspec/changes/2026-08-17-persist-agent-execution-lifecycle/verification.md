# 技术验证

## 验证环境

- 分支：`codex/persist-agent-execution-lifecycle`
- stacked base：`42fa088295b4fa34f71abff2803de807ddd393a3`
- Python：仓库 `.venv`
- 持久化集成测试：Testcontainers MySQL 8.4
- Java 回归：Maven + Testcontainers MySQL/Kafka

## TDD 证据

1. 首轮 Execution 规则与 MySQL RED：`26 passed, 14 failed`。失败暴露 initial history 未显式传递 `failure=None`。
2. 修正后：`10 passed, 5 failed`。剩余失败来自既有 Task 测试使用不存在的 Specialist Execution ID，新 FK 正确拒绝该夹具。
3. 将 Task 夹具调整为真实创建顺序后，Run/Task/Execution 局部 MySQL 回归：`40 passed`。
4. 独立审查发现 1 个 Important：transition request 首次查询 miss 后，并发赢家提交时，部分冲突分支没有二次按 request key 分类。`5be67a8` 已统一补上竞态重读，并增加 initial history 回滚与 600 字符 FAILED failure round-trip 测试。
5. 修复后 Execution 局部套件：`12 passed in 20.33s`。复审为 `0 Critical / 0 Important`。

## 最终命令与结果

| 命令 | 结果 |
|---|---|
| `python -m pytest contracts -q` | `99 passed in 0.90s` |
| `python -m pytest -q`（`services/agent-service`） | `106 passed in 166.79s` |
| `python -m ruff check .`（`services/agent-service`） | 通过 |
| `python -m ruff format --check .`（`services/agent-service`） | `42 files already formatted` |
| `mvn verify -q`（`backend/business-service`） | exit code 0；Surefire/Failsafe 共 20 份 XML，`65 tests, 0 failures, 0 errors, 0 skipped` |
| `git diff --check` | 通过 |
| `git diff --name-only 42fa088295b4fa34f71abff2803de807ddd393a3..HEAD` | 仅 OpenSpec、Agent Service migration/实现/测试；无 `dataset/` |

Java 日志中的 broker unavailable、连接失败与 migration failure 来自既有负向/恢复测试；Maven exit code 与 XML 汇总均成功。

## 可观察证据

- `agent_executions` 保存当前 snapshot、revision、result/failure 和不可变 provenance。
- `agent_execution_transitions` 按 `transition_request_id` 唯一，保存初始及后续 append-only history。
- 条件 UPDATE 只允许匹配 `execution_id + expected_status + expected_revision` 的请求推进。
- history 注入失败时，snapshot 创建或迁移在同一事务回滚。
- MySQL FK 拒绝缺失/跨 Run/role 不匹配的父关系，并以 `RESTRICT` 阻止删除被引用事实。

## 限制与验收状态

- 004 是严格升级：已有数据库若存在孤立 Run/Task Execution 引用会迁移失败，发布前必须审计并回填，不能自动置空。
- 本 Change 不包含 Worker claim/lease、自动 retry、Coordinator dispatch 或外部 API。
- 技术验证与独立审查完成，状态为 `review-handoff-ready`；Standard Learning Gate 与所有者最终 diff review 尚待 Review 会话完成。
