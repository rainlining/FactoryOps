# Review Handoff：2026-08-15-persist-agent-run-lifecycle

## 身份与恢复信息

- `change_id`: `2026-08-15-persist-agent-run-lifecycle`
- `learning_level`: `deep`
- `feature_branch`: `codex/persist-agent-run-lifecycle`
- `worktree`: `C:\\Users\\小霖\\Desktop\\work\\project2\\FactoryOps\\.worktrees\\persist-agent-run-lifecycle`
- `base_commit`: `a5e0da6`
- `reviewed_implementation_head`: `4cdbc4303fc28afac2e50504d77ec338294472a1`
- `branch_head`: 本 handoff 元数据提交；进入 Review 时以 `git rev-parse HEAD` 核对
- `status`: `review-handoff-ready`

Review 会话应切换到上述 worktree，先执行 `git status --short --branch` 和 `git log -1 --oneline`。在 Learning Gate 完成前，不得归档、合并 `main`，也不得与实现会话并发修改本 Change。

## 已实现范围

- 版本化 migration `002` 创建 `agent_runs` 当前快照和 append-only `agent_run_transitions`。
- 内部 Application Service 支持 original/replay 创建、读取和状态迁移。
- 创建与迁移分别实现唯一请求幂等、冲突分类和条件更新乐观锁。
- snapshot/history 在同一事务中提交；写事务回滚后才用新连接分类失败原因。
- Agent Run Contract 修正为允许启动前取消，但 SUCCEEDED/FAILED 仍要求 `started_at`。

明确不包含 Kafka Worker 接线、HTTP、Coordinator、Agent Runtime、checkpoint 内容、Resume/Replay 执行和 progress 更新。

## 关键设计决定

- original 以已经持久化的 Inbox `trigger_event_id` 唯一；replay 以 `replay_request_id` 唯一并保留 original lineage。
- 乐观锁同时匹配 `expected_status` 与 `expected_revision`，并发失败不自动重放业务意图。
- 每次迁移使用唯一 `transition_request_id`；同内容重试返回 duplicate-identical，不同内容返回 duplicate-conflicting。
- 时间由 Application Service 的 UTC clock 产生，一次操作只取一个 instant。
- Agent Service 内部实体使用数据库外键；Incident 只保存跨服务逻辑引用。

## 建议阅读顺序与真实调用链

1. `run_lifecycle/model.py`：命令、状态、结果类型。
2. `run_lifecycle/rules.py::plan_transition`：状态图、时间和 checkpoint 不变量。
3. `run_lifecycle/service.py::AgentRunLifecycleService`：事务编排和失败分类。
4. `run_lifecycle/repository.py::MySqlAgentRunRepository`：显式 SQL 边界。
5. `event_ingress/migrations/002_create_agent_run_lifecycle.sql`：Schema、索引、约束。
6. 两个 lifecycle 测试文件：真实 MySQL、并发和回滚证据。

original 成功链：`create_original_run` → 校验 Inbox 引用及 Contract → INSERT snapshot → INSERT `NULL → PENDING` history → commit → `get_run` 重建 Contract。

transition 成功链：`transition_run` → 读取 snapshot → `plan_transition` → 构造候选 snapshot 并执行 Contract 预校验 → 条件 UPDATE snapshot → INSERT history → commit → 返回 applied。

transition 失败链：条件 UPDATE 未命中或唯一键冲突 → 原写事务 rollback → `_classify_failed_transition` 在新连接读取已提交事实 → 返回 duplicate-identical、duplicate-conflicting 或 concurrency-conflict。

## 验证证据

完整命令、数量和限制见 `verification.md`。交接时的结果是 Python 48 passed、Contract 57 passed、Java 65 passed，并且 Ruff 与 `git diff --check` 通过。

独立审查无 Critical。审查发现的 replay 分类顺序和 Clock 回拨写入两项 Important 已在 `4cdbc43` 修复；对应测试分别证明 conflicting 分类不会被 lineage 校验遮蔽，以及非法终态不会改变 snapshot revision/history。

## Deep Learning 任务

Owner 修改：选择一条合法或非法迁移边，修改 `rules.py` 的真实状态图并添加精确领域测试；必须说明业务语义和终态影响。Review 会话应先把候选边缩小到不会削弱生产安全规则的选项。

Failure/Debug A：运行或断点观察两个相同 revision 的并发迁移，确认仅一个 applied，另一个 concurrency-conflict，并检查最终 revision/history 数量。

Failure/Debug B：使用现有 SQLAlchemy 故障注入让 history INSERT 失败，确认 snapshot 状态、revision 和 history count 全部保持原值；完成后移除或关闭注入并重跑测试。

Learning Gate 仍为 pending。Review 会话必须完成真实 Walkthrough、Owner 修改、两项故障实验、最终 diff review 与明确接受，才能把 Change 标记 completed。
