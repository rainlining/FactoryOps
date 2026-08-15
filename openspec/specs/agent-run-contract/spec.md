# Agent Run Contract 规格增量

### Requirement: Workflow Run 与 Agent Execution 必须是不同概念

系统必须使用 Workflow Run 表示一个 Quality Incident 的完整多 Agent 工作流，并将单个 Coordinator 或 Specialist Agent 的执行保留为后续独立 Contract。

#### Scenario: Run 只引用执行对象

- **WHEN** 一个 Workflow Run 已产生 Coordinator Execution 或 Checkpoint
- **THEN** Run 只保存相应 ID 引用和进度摘要
- **AND** 不内嵌 Agent Execution、Task 或 Checkpoint 的完整内容

### Requirement: original Run 必须以触发事件幂等

每个 `trigger_event_id` 必须只对应一个 original Workflow Run。`run_id` 只用于稳定引用，不能替代触发事件的幂等语义。

#### Scenario: 合法 original Run

- **WHEN** `run_kind` 为 `original`
- **THEN** `original_run_id` 必须等于自身 `run_id`
- **AND** 必须具有 `trigger_event_id`
- **AND** 不得具有 `replayed_from_run_id` 或 `replay_request_id`

### Requirement: replay Run 必须保留完整血缘

每个 replay 必须创建新的 Run，不得修改历史 Run，并以 `replay_request_id` 表达重放请求幂等性。

#### Scenario: 合法 replay Run

- **WHEN** `run_kind` 为 `replay`
- **THEN** 必须具有 `original_run_id`、`replayed_from_run_id` 和 `replay_request_id`
- **AND** `run_id` 不得等于两个血缘引用中的任意一个
- **AND** 不得具有 `trigger_event_id`

#### Scenario: replay 基于另一个 replay

- **GIVEN** original A 派生 replay B
- **WHEN** replay C 直接基于 B 创建
- **THEN** C 的 `original_run_id` 必须指向 A
- **AND** C 的 `replayed_from_run_id` 必须指向 B

### Requirement: Run 必须冻结执行 Provenance

Run 创建时必须记录 Incident、Runtime、Workflow、Prompt Set、Model Policy、Tool Policy、Context Policy 和代码 revision 的实际版本或引用。这些字段必须是不可变事实，且 replay 必须记录自己的实际配置。

#### Scenario: replay 使用不同配置

- **WHEN** replay 为对比实验选择了不同 Prompt 或 Model Policy
- **THEN** replay 必须记录新版本
- **AND** original Run 的 Provenance 不得被修改

### Requirement: Lifecycle 必须使用受限状态和一致时间语义

状态必须属于 `PENDING`、`RUNNING`、`WAITING_FOR_APPROVAL`、`SUSPENDED`、`SUCCEEDED`、`FAILED`、`CANCELLED`。后三者必须是终态。

#### Scenario: 非终态快照

- **WHEN** Run 处于非终态
- **THEN** 不得具有 `ended_at`

#### Scenario: 终态快照

- **WHEN** Run 处于终态
- **THEN** 必须具有 `started_at` 和 `ended_at`
- **AND** `ended_at` 不得早于 `started_at`

#### Scenario: 进度摘要有效

- **WHEN** Run 声明任务总数和完成数
- **THEN** `completed_task_count` 不得大于 `task_count`
- **AND** 摘要不得取代 Task Contract 的事实来源地位

### Requirement: Contract 必须严格版本化

Contract v1.0.0 的所有结构化对象必须拒绝未知字段。Consumer 必须显式声明支持的版本，不得通过静默忽略字段推断兼容。

#### Scenario: 未知字段或不支持版本

- **WHEN** 输入包含未知字段或不支持的 `contract_version`
- **THEN** Validator 必须在任何关系分类前拒绝输入
- **AND** 返回可定位的错误码与 JSON path

### Requirement: Evaluation ground truth 必须隔离

Workflow Run Contract 不得包含 Evaluation ground truth、期望答案或仅用于离线评分的标签。

#### Scenario: ground truth 泄漏

- **WHEN** 输入尝试加入 `ground_truth` 等未声明评测字段
- **THEN** 严格 Schema 必须拒绝输入
