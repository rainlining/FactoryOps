# 技术设计：Agent Run Lifecycle Persistence

## 1. 架构结论

本 Change 在 Agent Service 内新增独立 `run_lifecycle` 模块。它使用 SQLAlchemy Core 和显式 SQL，不引入 ORM，不连接 Kafka Worker、HTTP 或 Coordinator。

```text
Application Service
├── create_original_run
├── create_replay_run
├── transition_run
└── get_run
        │
        ▼
MySQL transaction
├── agent_runs              当前快照
└── agent_run_transitions   append-only history
```

## 2. 数据所有权

Agent DB 内部拥有 Inbox、Run 和 Transition。`incident_id` 只保存 Kafka 事实中的逻辑引用，不跨服务建立到 Java Business DB 的外键。Agent 内部外键全部 `ON DELETE RESTRICT`，Application Service 不提供删除入口。

## 3. 创建事务

Original 和 replay 都由 Lifecycle Service 生成 `run_id`、`transition_id`、初始 transition request ID 和单一 UTC 时间。调用方不能提供实体 ID 或创建时间。

```text
BEGIN
INSERT agent_runs(PENDING, revision 0)
INSERT agent_run_transitions(NULL, PENDING, NULL, 0)
COMMIT
```

唯一键冲突必须使整个事务回滚。随后用新事务读取赢家记录，并只比较调用方可控的不可变输入；服务生成 ID、时间不参与 identical/conflicting 判断。

## 4. Replay 血缘

数据库自引用外键只证明引用存在。Application Service 还必须验证根记录为 ORIGINAL、直接来源拥有相同 `original_run_id`，并且根、来源和命令 `incident_id` 相同。identity/provenance 创建后没有更新入口，因此校验后不会发生血缘漂移。

## 5. 合法迁移图

```text
PENDING → RUNNING | CANCELLED
RUNNING → WAITING_FOR_APPROVAL | SUSPENDED | SUCCEEDED | FAILED | CANCELLED
WAITING_FOR_APPROVAL → RUNNING | SUSPENDED | CANCELLED
SUSPENDED → RUNNING | FAILED | CANCELLED
SUCCEEDED | FAILED | CANCELLED → 无出边
```

进入 `SUSPENDED` 必须具有 `latest_checkpoint_id` 和 reason code。Checkpoint 实体存在性留给后续 Contract 与 Resume Change。

## 6. 乐观锁与幂等

迁移 SQL 同时匹配 expected status/revision。UPDATE 和 history INSERT 必须同事务。任何失败都回滚后，才在新事务按 `transition_request_id` 分类：existing identical、existing conflicting 或真正 concurrency conflict。原因是 MySQL 默认 REPEATABLE READ 的旧快照不适合在失败事务中读取刚提交记录。

## 7. 时间与状态原因

可注入 UTC Clock 每次只生成一个时间。创建时 `created_at == updated_at == initial occurred_at`；迁移时 `updated_at == occurred_at`。首次启动设置 `started_at`，终态设置 `ended_at`。启动前取消不伪造 `started_at`。

初始 PENDING snapshot 可无 reason；每条 transition 都有 Actor/Reason，后续 snapshot 保存形成当前状态的最新 reason。

## 8. 字段更新边界

迁移只更新 status、revision、updated/started/ended 时间、status reason，以及进入 SUSPENDED 时的 checkpoint ID。identity、provenance、coordinator execution 和 progress 不进入状态更新 SQL。

## 9. 索引

- Run：主键 run ID；唯一 trigger event、replay request；复合索引 incident/created、original/created、status/updated。
- Transition：主键 transition ID；唯一 transition request；唯一 run/to revision。
- 不为 Actor、Reason 或自由文本提前加索引。

## 10. 失败路径

- Inbox 不存在或内部引用不存在：外键/应用校验拒绝。
- Run INSERT 后 history INSERT 失败：整个创建事务回滚。
- Snapshot UPDATE 后 history INSERT 失败：UPDATE 回滚。
- 条件 UPDATE 为 0：新事务区分 duplicate 与 concurrency conflict。
- 相同 request ID 不同命令：conflicting，不覆盖历史。
- 非法迁移、终态迁移或 SUSPENDED 缺 Checkpoint：SQL 前拒绝。
- 读取到不符合 Contract 的列：PersistenceIntegrityError。

## 11. 被放弃的方案

- 只保存当前快照：无法解释恢复和状态来源。
- JSON blob：关键唯一键、查询和更新边界不可见，并形成双重事实风险。
- 跨 Business DB 外键：破坏服务所有权与独立部署。
- `SELECT FOR UPDATE` 包围业务决策：可能在 LLM/Tool 调用期间持锁。
- Redis 分布式锁：当前竞争在单一 MySQL 聚合内，增加不必要 Lease 失败模型。
- ORM：掩盖本 Change 需要学习的精确 SQL、rowcount 和事务回滚。
- 通用 patch：允许绕过未来 Agent Execution、Task 和 Checkpoint Contract。
- 级联或软删除：当前没有删除语义且会破坏审计。

## 12. 测试策略

领域单元测试覆盖状态图、时间和 Suspended 规则。MySQL 8.4 集成测试覆盖 Schema、迁移升级、创建/迁移原子性、唯一约束、外键、血缘、乐观锁、请求幂等和失败回滚。Contract 回归覆盖取消时间修正。
