# Agent Execution Contract 规格增量

### Requirement: Workflow Run 与单次 Agent Execution 必须保持所有权分离

一个 Agent Execution 必须属于且只属于一个 Workflow Run，并表示一个 Agent 角色的一次 attempt。Contract 不得内嵌完整 Run、Task、Context、Prompt、模型响应或大型 Artifact。

#### Scenario: Coordinator 首次执行

- **WHEN** Coordinator 为一个 Run 创建第一次执行
- **THEN** `agent_role` 为 `coordinator` 且 `attempt` 为 1
- **AND** 输入、输出和 Task 仅以稳定引用表达

### Requirement: Execution 身份必须支持确定性幂等

`execution_id` 必须是稳定对象引用；`execution_key` 必须由 `run_id`、`agent_role` 和正整数 `attempt` 按规范形式计算。相同 key 不得代表不同 immutable input。

#### Scenario: 相同 attempt 重投

- **WHEN** 相同 Run、角色、attempt 和不可变输入再次到达
- **THEN** canonical relation 必须分类为 `duplicate-identical`

#### Scenario: 幂等 key 与字段不一致

- **WHEN** `execution_key` 不是规范字段的确定性摘要
- **THEN** Validator 必须在持久化或执行前拒绝

### Requirement: Execution 必须冻结实际执行 Provenance

每个 Execution 必须记录实际使用的 Prompt、Model、Tool、Context Policy、Runtime 和代码 revision。引用不得从父 Run 静默推断或在 retry 时覆盖历史 attempt。

#### Scenario: retry 更换模型策略

- **WHEN** retry attempt 使用新的 Model Policy
- **THEN** 新 Execution 记录自己的版本
- **AND** 旧 Execution 保持不变

### Requirement: 生命周期必须保持结果与失败互斥

状态必须属于 `PENDING`、`RUNNING`、`SUCCEEDED`、`FAILED`、`CANCELLED`。`SUCCEEDED` 必须有 result 且不得有 failure；`FAILED` 必须有 failure 且不得有 result；其他状态不得提前携带终态结果。

#### Scenario: 可重试执行失败

- **WHEN** 一次执行以可安全重试的技术错误结束
- **THEN** 状态为 `FAILED`
- **AND** failure 的 `recoverability` 为 `retryable`
- **AND** retry 必须创建 attempt + 1 的新 Execution，不得改写失败记录

#### Scenario: 结束时间早于开始时间

- **WHEN** `ended_at` 早于 `started_at`
- **THEN** Validator 必须拒绝

### Requirement: 输入和输出必须使用受限结构化引用

输入必须分别保存 task、context snapshot 和 evidence 引用；成功结果必须使用 output artifact、decision 和 evidence 引用。引用数组不得重复，且 Coordinator 以外的执行必须具有 `task_id`。

#### Scenario: Specialist 缺少 Task

- **WHEN** Quality、Production、SLA 或 Risk Execution 没有 `task_id`
- **THEN** Validator 必须拒绝

### Requirement: Contract 必须严格版本化并隔离 Evaluation ground truth

v1.0.0 所有对象必须拒绝未知字段。Contract 不得包含 ground truth、expected action 或仅用于离线评分的标签。

#### Scenario: ground truth 泄漏

- **WHEN** payload 加入 `ground_truth`
- **THEN**严格 Schema 必须拒绝并返回可定位 JSON path

### Requirement: Revision 关系必须区分合法演进和冲突

两份合法 Contract 只有在 identity 与不可变内容一致、revision 精确增加且生命周期时间不倒退时，才能分类为 `same-execution-next-revision`。同 ID 的相同快照为 `duplicate-identical`，其余同 ID 合法 payload 为 `duplicate-conflicting`，不同 ID 为 `distinct`。

#### Scenario: 同一 Execution 的下一快照

- **WHEN** `PENDING / revision 0` 合法推进到 `RUNNING / revision 1`
- **THEN** 关系分类为 `same-execution-next-revision`

#### Scenario: 跳过 revision

- **WHEN** 同一 Execution 从 revision 0 跳到 revision 2
- **THEN** 关系分类为 `duplicate-conflicting`
