# Change 设计：2026-08-16-define-agent-execution-contract

## 设计目标

建立可由持久化、Coordinator、Trace 和 Evaluation 共同消费的 Agent Execution v1.0.0，明确“一次角色 attempt”的身份、输入、版本、状态、成功结果和失败事实。

## 边界与所有权

- Workflow Run 拥有完整 Incident Workflow；Agent Execution 通过 `run_id` 归属 Run。
- Execution 拥有单角色单 attempt 的冻结输入/Provenance、生命周期和终态结果。
- Task、Context Snapshot、Evidence、Artifact 和 Decision 各自拥有完整内容；Execution 只保存引用。
- Contract 层不读取数据库、不领取 Run、不调用 Agent，也不决定 retry。

```text
Workflow Run
  ├── Coordinator Execution attempt 1
  ├── Quality Execution attempt 1 -> FAILED retryable
  └── Quality Execution attempt 2 -> SUCCEEDED
```

## 数据流或控制流

1. 后续 Coordinator Runtime 从已持久化 Run 与 Task 组装不可变 Execution 输入。
2. 调用方计算规范 `execution_key`，构造 `PENDING / revision 0` Contract。
3. Validator 先验证版本与 Schema，再检查 key、角色/Task、时间和引用唯一性。
4. 持久化 Change 将以 key 唯一约束分类重复；本 Change 的 relation classifier 提供规范语义。
5. Lifecycle 每次成功变更 revision 精确加一；成功保存 result，失败保存 failure。
6. retry 复制必要输入并使用 attempt + 1 创建新 execution_id/key，保留旧失败事实。

## 状态、事务与不变量

- 状态：`PENDING -> RUNNING -> SUCCEEDED|FAILED|CANCELLED`；允许 `PENDING -> CANCELLED`。完整状态图由后续持久化 Change执行，本 Contract 约束快照形状。
- 事务：N/A，本 Change 不持久化。后续 snapshot/history 必须共享事务。
- `attempt >= 1`；key 必须等于规范 SHA-256 摘要。
- immutable 区域在 revision 演进中不得变化。
- `SUCCEEDED` 仅有 result；`FAILED` 仅有 failure；`CANCELLED` 两者皆无。
- Specialist 必须有 Task；Coordinator 可以没有 Task。
- 引用数组有稳定顺序、非空值且无重复。
- 并发：Contract 不选 owner；relation classifier 只识别相邻 revision，不能替代数据库乐观锁。

## 失败路径

- 不支持版本：Schema 加载前拒绝，不可重试配置错误。
- 未知/ground-truth 字段：Schema 拒绝，不进入 Agent Context。
- key 不匹配：拒绝，防止幂等键与真实身份分裂。
- Specialist 无 Task、引用重复：拒绝，属于确定性输入错误。
- 非法终态形状或时间倒序：拒绝，属于完整性错误。
- 同 ID immutable 内容变化、revision 跳跃或时间回退：关系分类为 conflicting，不覆盖。
- failure 的 `recoverability=retryable` 只是分类事实；运行时仍须按 Tool/Model Policy 决定是否创建下一 attempt。

## 测试与可观测性策略

- 单元/Contract Test：Schema 严格性、Validator 语义、canonical key 和 relation classifier。
- 集成测试：N/A，无持久化或传输适配器。
- 失败测试：ground truth、key mismatch、specialist missing task、result/failure conflict、timestamp order、duplicate refs、revision jump。
- 证据：固定 fixture、错误码、JSON path、pytest 结果和 `git diff --check`。

## 方案比较与决定

- 选择独立 Agent Execution Contract，而非扩充 Run：避免 Workflow 与单次调用生命周期耦合。
- 选择 attempt 为新对象，而非同对象 `retry_count`：保留每次 Prompt/Model/输出/失败 Provenance。
- 选择 SHA-256 规范 key，而非调用方自由 UUID：能够重建、审计并识别同一 attempt。
- 选择显式版本字段，而非从 Run 继承：Agent retry 或 specialist 可使用不同实际策略，不能静默推断。
- 选择引用而非内嵌内容：避免 Contract 膨胀、循环版本依赖和 Artifact 进入 MySQL。
- 选择单步 revision relation，而非只比较全量相等：为后续乐观锁提供明确语义。

## 连续 Apply 计划

1. 工件和失败测试：验证 OpenSpec 结构并提交。
2. Schema 与 fixtures：先观察缺失模块失败，再实现严格 v1.0.0 并提交。
3. Validator/key/relation：从失败测试推进，固定错误边界并提交。
4. README、全量验证和独立审查：修复 Critical/Important 后完成 handoff 并推送。
