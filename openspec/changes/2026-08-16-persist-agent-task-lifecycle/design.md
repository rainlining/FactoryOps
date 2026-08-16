# Change 设计：2026-08-16-persist-agent-task-lifecycle

## 边界与所有权

- `AgentTaskLifecycleService` 拥有创建/迁移编排、幂等分类与 Contract 重建。
- `rules.py` 拥有纯状态、attempt、结果和时间规则。
- `MySqlAgentTaskRepository` 只拥有 SQL、事务和条件更新，不复制领域状态机。
- Agent Task Contract Validator 是出入持久化边界的最终结构与关系校验。
- MySQL 拥有唯一约束、Run/Task 依赖引用完整性和 snapshot/history 原子提交。

## 数据模型

- `agent_tasks`：当前 snapshot；不可变 assignment/input 与可变 lifecycle/execution/result 分列保存。
- `agent_task_dependencies`：`task_id, dependency_task_id, ordinal`，保留 Contract 数组顺序并以主键禁止重复。
- `agent_task_transitions`：append-only history，记录 request、revision、状态、actor、reason、Execution、结果和时间。
- evidence refs 使用 JSON 数组。它们是有序、受 Contract 限长的外部逻辑引用，当前没有可建立 FK 的本地实体；依赖则需要查询与 FK，故正规化为 junction table。

## 创建数据流

1. 先按 `task_request_id` 查询并分类已有事实。
2. 生成 Task ID/key/time，构造 PENDING Contract 并执行 Validator。
3. Repository 在事务内锁定并校验父 Run与全部依赖，随后写 snapshot、依赖、initial history。
4. 唯一键竞争时重新读取赢家，分类 identical/conflicting。

## transition 数据流

1. 先按 `transition_request_id` 查询历史，处理重投。
2. 读取当前 snapshot；status/revision 不符直接分类 concurrency conflict。
3. 纯规则根据命令构造下一 snapshot；Service 用 Validator 验证候选 Contract。
4. Repository 在一个事务内执行带 expected status/revision 的条件 UPDATE，然后 INSERT history。
5. 条件更新失败重新查询 request key；history 失败使整个事务回滚。

## 状态、不变量与事务

- 合法边沿用 Agent Task Contract：PENDING→RUNNING/CANCELLED/SKIPPED；RUNNING→RUNNING/SUCCEEDED/FAILED/CANCELLED；终态不可离开。
- RUNNING→RUNNING 必须切换到新的 Execution ID并将 attempt_count 加一；首次 RUNNING 设置 started_at。
- SUCCEEDED/FAILED 必须引用当前 Execution；FAILED 必须为 `non_retryable`。
- identity、assignment、input 和 created_at 在迁移中不可变。
- `updated_at` 单调不减；ended_at 不早于 started_at。
- 创建事务覆盖 snapshot、dependencies、initial history；迁移事务覆盖 conditional snapshot update 与 history。

## 并发和幂等

- 创建唯一键：`task_request_id` 与 `task_key`；二者均代表 Run 内稳定 dispatch 请求。
- transition 唯一键：`transition_request_id`；`(task_id, to_revision)` 保证每个 revision 最多一条历史。
- 乐观锁 predicate：`task_id + expected_status + expected_revision`。不同请求竞争时最多一个赢家。
- 本 Change 不 claim Task，不建立 lease owner；Worker ownership 属于后续 Change。

## 失败与恢复

- 不存在父 Run、依赖不存在/跨 Run/自依赖：创建拒绝，无部分写入。
- 重投 payload 不同：稳定返回 conflicting，不覆盖首次事实。
- stale revision：返回 concurrency conflict，并携带当前 snapshot（存在时）。
- 非法状态、attempt、结果或时钟回退：在写库前拒绝。
- 数据库行不能通过 Contract Validator：抛 `PersistenceIntegrityError`，促使运维修复数据或 migration。

## 测试与可观测性

- 纯规则单元测试覆盖全部边、attempt、终态和时间。
- Testcontainers MySQL 集成测试覆盖 migration、FK/unique/check、事务、并发及失败注入。
- history 提供 actor/reason/revision/Execution 可审计证据；verification 记录 SQL 行数和 pytest 结果。

## 被放弃的方案

- 单表 JSON snapshot：查询、约束和乐观锁证据较弱，拒绝。
- 依赖仅存 JSON：无法建立 FK 或可靠验证跨 Run，拒绝。
- 先建立虚假的 Execution 表/FK：扩大范围且与后续 Execution persistence 设计冲突，拒绝。
- 用数据库 trigger 实现状态机：规则难以单测且与 Contract Validator 重复，拒绝。
- transition-only event sourcing：当前恢复和查询需要额外投影机制，超出本 Change。
