# Review Handoff：2026-08-16-persist-agent-task-lifecycle

## 元数据

- `change_id`: `2026-08-16-persist-agent-task-lifecycle`
- `learning_level`: `standard`
- `status`: `review-handoff-ready`
- `feature_branch`: `codex/persist-agent-task-lifecycle`
- `worktree`: `C:\Users\小霖\Desktop\work\project2\FactoryOps\.worktrees\persist-agent-task-lifecycle`
- `stacked_on_branch`: `codex/define-agent-task-contract`
- `stacked_base_commit`: `b39970ffb81c4051e64ca1a32d46ed6a89247595`
- `reviewed_implementation_head`: `f1c48f5`
- `handoff_metadata_commit`: 本文件所在最终文档 commit

## 实现与非目标

已实现 Agent Task 的 MySQL snapshot、dependency junction、append-only history、创建/transition 请求幂等、同 Run 依赖校验、revision 乐观锁、attempt/终态规则、Contract 重建，以及真实 MySQL 并发和事务失败测试。

非目标：Execution 持久化/FK、Coordinator Worker、dispatch/lease、retry policy、Checkpoint/Resume、LLM/Tool、Java API、审批、Evaluation 和 `dataset/`。

## 关键决定

- 延续首次 deep Run persistence 的 snapshot + history、同事务、唯一键和条件 UPDATE 模式。
- 依赖使用 junction table 与 Task FK；Evidence 保留有序 JSON 外部引用。
- Service 负责领域编排和 Contract Validator；Repository 负责 SQL/事务；rules 负责纯状态规则。
- Execution 引用暂为 Contract 校验后的逻辑引用，后续 Execution persistence migration 再加同库 FK。

## 真实入口与调用链

创建成功链：`AgentTaskLifecycleService.create_task` → `compute_task_key` → `_validate/_to_contract` → `validate_task` → `MySqlAgentTaskRepository.create` → 父 Run/依赖 `FOR SHARE` 校验 → INSERT task/dependencies/initial transition → reload + Contract 验证。

迁移成功链：`transition_task` → request lookup → current snapshot → `plan_transition` → candidate Contract 验证 → `apply_transition` 的 status/revision 条件 UPDATE + history INSERT → reload。

失败链：依赖缺失/跨 Run 抛 `TaskCreationRejected`；非法边/attempt/时间抛 `LifecycleRuleViolation`；条件更新 miss 二次查询 request 后分类 duplicate 或 concurrency conflict；history INSERT 异常触发事务回滚；非法数据库行在 `_to_contract` 抛 `PersistenceIntegrityError`。

建议测试入口：`test_task_lifecycle_rules.py` 先看状态图；`test_task_lifecycle_mysql.py` 再看创建、依赖、retry、并发、回滚和损坏数据。

## 修改文件

- migration：`event_ingress/migrations/003_create_agent_task_lifecycle.sql` 与 runner。
- 生产代码：`task_lifecycle/model.py`、`rules.py`、`repository.py`、`service.py`。
- 测试：Task rules/MySQL tests，并更新 Run migration 版本断言。
- OpenSpec：proposal/spec/design/technical decisions/tasks/learning/verification/handoff。

## 验证与审查

- Task persistence 18 passed；全部 Agent 93 passed；Ruff check/format 通过。
- 全部 Contract 97 passed；Java 65 passed。
- 独立审查修复 2 Important：取消重投分类、残留 result 字段完整性；当前 0 Critical/Important。
- 完整命令、RED 证据与限制见 `verification.md`。

## 三个 Change 的 Review 顺序

1. `2026-08-16-define-agent-execution-contract`。
2. `2026-08-16-define-agent-task-contract`。
3. `2026-08-16-persist-agent-task-lifecycle`。

任一上游 Review/Learning 产生 commit，下游 stacked branch 必须吸收最终 commit 并重跑其验证。三个 Change 可以在同一 Review 会话依次处理，但各自的 Learning Gate 与 owner 接受不能合并省略。三个 worktree 不得被多个会话并发修改。

## Standard Learning 要点

- 解释 snapshot/dependencies/history 的两个事务边界。
- 定位 identical/conflicting/concurrency-conflict 三类结果的实际分支。
- 解释 retry 为什么更新同一 Task 但切换 Execution。
- 解释 Execution ID 为什么暂时没有 FK，以及应在哪个后续 migration 补齐。
- 可选 Owner 修改：调整一个非安全关键 priority 测试边界并跑局部测试。

## 恢复命令

```powershell
cd C:\Users\小霖\Desktop\work\project2\FactoryOps\.worktrees\persist-agent-task-lifecycle
git status --short --branch
git log --oneline b39970f..HEAD
git diff --stat b39970f..HEAD
cd services/agent-service
python -m pytest tests/test_task_lifecycle_rules.py tests/test_task_lifecycle_mysql.py -q
```

本 worktree 现在只供 Review/Learning 使用。Learning Gate 与 owner 最终接受前，不得归档、合并 `main` 或删除 branch/worktree。

## Review/Learning 会话增量（2026-08-17）

- 已完成创建、transition、并发冲突、事务回滚和 Contract 重建调用链 Walkthrough。
- 已吸收两个上游 Contract 的 Review commits。
- 为兼容 Task `failure.message` 600 上限，snapshot/history 两列扩为 `VARCHAR(600)`，并新增真实 MySQL round-trip 测试。
- 增量验证：Task persistence 19 passed；全部 Contract 99 passed；完整 Agent Service 94 passed；Java `mvn verify` 退出码 0；Ruff 通过。
- Standard 调试实验已由真实 MySQL 测试覆盖；最终 diff 接受仍需项目所有者明确确认。
