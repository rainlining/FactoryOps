# Review Handoff

## 恢复信息

- Change：`2026-08-17-persist-agent-execution-lifecycle`
- 学习等级：`standard`
- 状态：`review-handoff-ready`
- feature branch：`codex/persist-agent-execution-lifecycle`
- worktree：`C:\\Users\\小霖\\Desktop\\work\\project2\\FactoryOps\\.worktrees\\persist-agent-execution-lifecycle`
- base commit：`42fa088295b4fa34f71abff2803de807ddd393a3`
- reviewed implementation head：`5be67a8`
- final handoff commit：以该分支远端 HEAD 为准

恢复命令：

```powershell
git -C 'C:\Users\小霖\Desktop\work\project2\FactoryOps\.worktrees\persist-agent-execution-lifecycle' status
git -C 'C:\Users\小霖\Desktop\work\project2\FactoryOps\.worktrees\persist-agent-execution-lifecycle' log --oneline 42fa088..HEAD
```

该分支堆叠在 `codex/persist-agent-task-lifecycle` 上；Review 期间禁止其他会话并发修改此 Change/worktree。上游 Execution Contract、Task Contract 和 Task Persistence 的 Review commits 已包含在 base 中，但两个 Deep Contract Change 的 Owner 亲自修改尚未完成，仍不得归档或合并 `main`。

## 已实现范围

- `agent_executions` snapshot 与 `agent_execution_transitions` append-only history。
- 以 Contract `execution_key` 创建幂等，以 `transition_request_id` 迁移幂等。
- `execution_id + expected_status + expected_revision` 乐观并发控制。
- Coordinator/Specialist 的 Run、Task、role 父关系校验。
- migration 004 补齐 Execution → Run/Task，以及 Run/Task → Execution 的双向 FK，删除策略为 `RESTRICT`。
- migration 004 在任何 DDL 前审计既有反向 Execution 引用，失败后不会留下无法重跑的半套表。
- 数据库 CHECK 与 Service 重建双层拒绝终态 result/failure 残留列，避免脏数据被静默洗白。
- 创建和迁移的 snapshot/history 同事务原子性，包含并发赢家重读分类。

非目标：Worker claim/lease、自动 retry、Coordinator dispatch、LLM/Tool、Checkpoint/Resume/Replay、Java Business API、Evaluation 与 `dataset/`。

## 关键文件与 Walkthrough 路线

建议按以下顺序阅读：

1. `proposal.md`、`design.md`、`technical-decisions.md`：范围、创建顺序、事务与升级取舍。
2. `services/agent-service/src/factoryops_agent_service/event_ingress/migrations/004_create_agent_execution_lifecycle.sql`：表、唯一键和双向 FK。
3. `execution_lifecycle/model.py`：创建/迁移命令及结果类型。
4. `execution_lifecycle/service.py::create_execution`：`compute_execution_key` → Contract 构造 → `_validate` → Repository 父关系检查 → snapshot + initial history。
5. `execution_lifecycle/service.py::transition_execution`：request 幂等查询 → current snapshot → `plan_transition` → candidate Contract validation → 条件更新 + history → 竞态重读分类。
6. `execution_lifecycle/rules.py::plan_transition`：合法状态边、时间单调、result/failure 终态规则。
7. `execution_lifecycle/repository.py::create/apply`：事务、父记录锁、条件 UPDATE 和 history 插入。
8. `tests/test_execution_lifecycle_rules.py` 与 `tests/test_execution_lifecycle_mysql.py`：成功链、父关系失败、重复请求、stale revision、并发与事务回滚。

业务创建顺序是不变量：Run → Coordinator Execution → Task → Specialist Execution → Task RUNNING。Coordinator 必须 `task_id=null`；Specialist 必须引用同 Run 且 `target_agent_role` 匹配的 Task。

## 验证与审查

- Contract：99 passed。
- Agent Service：109 passed；Ruff check/format 均通过。
- Java 回归：65 tests，0 failure/error/skipped。
- `git diff --check` 通过；相对 base 无 `dataset/` 修改。
- 实现期独立审查发现的 1 个 Important 竞态分类问题已在 `5be67a8` 修复。
- Review/Learning 会话发现并修复 2 个 Important：终态残留列静默隐藏、004 DDL 失败后不可重跑。新增 3 个回归测试；复审无未处理 Critical/Important。
- 完整命令、TDD RED 记录和证据见 `verification.md`。

## Review/Learning 待办

- stale revision、并发赢家、history rollback 与 migration preflight recovery 已实际运行并通过。
- 解释创建幂等、transition request 幂等、revision 冲突三类结果为何不同。
- 解释双向 FK 为什么要求固定创建顺序，以及严格 migration 遇到孤立引用为何选择失败。
- 沿一次成功创建和一次并发迁移失败调用链定位上述真实符号。
- Review 最终 diff 并明确接受或提出修改。

本 Change 是 `standard`，不要求强制 Owner 修改或 Deep failure/debug exercise。完成上述 review 前不得标记 `completed`、归档或并入 `main`。
