# Change 提案：2026-08-17-persist-agent-execution-lifecycle

## 元数据

- `change_id`: `2026-08-17-persist-agent-execution-lifecycle`
- `status`: `review-handoff-ready`
- `learning_level`: `standard`
- `first_deep_reference`: `2026-08-15-persist-agent-run-lifecycle`
- `depends_on`: `[2026-08-16-define-agent-execution-contract, 2026-08-16-define-agent-task-contract, 2026-08-16-persist-agent-task-lifecycle]`
- `stacked_base_commit`: `42fa088295b4fa34f71abff2803de807ddd393a3`
- `feature_branch`: `codex/persist-agent-execution-lifecycle`

## 动机与范围

Run 与 Task 已持久化，但每次 Coordinator/Specialist attempt 仍只有 Contract，没有可恢复快照、审计历史或数据库引用完整性。本 Change 新增 Execution snapshot/history、创建幂等、revision 乐观锁、Run/Task 父关系校验，并补齐 Run/Task 到 Execution 的同库 FK。

## 非目标

- Worker claim/lease、自动 retry、Coordinator dispatch、模型或 Tool 调用。
- Context/Artifact/Decision 实体、Checkpoint/Resume/Replay。
- Java Business API、审批、业务副作用、Evaluation 和 `dataset/`。

## 学习等级

`standard`。复用首次 deep Run persistence 的 snapshot/history、同事务、唯一键与乐观锁模式；新增角色/Task 父关系、attempt key、result/failure 和双向 FK，但不引入新的分布式 ownership 或跨库事务。

## 升级限制

004 migration 会把先前 Task/Run 中的逻辑 Execution 引用升级为 FK。若现存数据库有孤立引用，migration 必须失败并要求先审计/回填；不得自动置空审计事实。
