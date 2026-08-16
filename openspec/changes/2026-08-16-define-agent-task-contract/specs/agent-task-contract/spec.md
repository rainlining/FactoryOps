# Agent Task Contract 规格增量

### Requirement: Task 必须独立于 Run 与 Execution

Task 必须属于一个 Workflow Run，由一个 Coordinator Execution 创建，并表达一个专业角色的稳定工作要求。Task 不得内嵌完整 Run、Execution、Context 或 Artifact。

#### Scenario: Quality Task 被分派

- **WHEN** Coordinator 创建 `QUALITY_ANALYSIS` Task
- **THEN**目标角色必须为 `quality`
- **AND** 后续 retry 必须在同一 Task 下创建新的 Execution attempt

### Requirement: dispatch 必须在 Run 内幂等

调用方必须提供稳定 `task_request_id`；`task_key` 必须由 Contract 版本、`run_id` 和 request ID 确定性计算。相同 request 不得创建不同 Task 内容。

#### Scenario: Coordinator 崩溃后重放 dispatch

- **WHEN** 使用相同 Run、request ID 和不可变内容重试
- **THEN** 关系分类必须识别 identical duplicate

### Requirement: Task type 与目标角色必须匹配

`QUALITY_ANALYSIS→quality`、`PRODUCTION_ANALYSIS→production`、`SLA_ANALYSIS→sla`、`RISK_ASSESSMENT→risk`。v1 不允许 Coordinator 自派 Task 或动态角色。

### Requirement: 依赖必须可追溯且不得自引用

Task 输入必须包含 Context Snapshot、Evidence 和依赖 Task 引用。单条 Contract 必须拒绝自身出现在依赖中；跨记录存在性、同 Run 和环检测由后续持久化层负责。

### Requirement: 终态必须引用真实 Execution 事实

状态必须属于 `PENDING`、`RUNNING`、`SUCCEEDED`、`FAILED`、`CANCELLED`、`SKIPPED`。成功必须引用成功 Execution；失败必须引用最终失败 Execution；取消或跳过不得伪造 completion/failure。

#### Scenario: retryable Execution 失败但 Task 尚可重试

- **WHEN** 某 attempt 失败但 policy 允许 retry
- **THEN** Task 可保持 `RUNNING`
- **AND** 不得提前写入 Task failure

#### Scenario: Task 已进入 FAILED 终态

- **WHEN** retry policy 已决定 Task 不再创建 attempt
- **THEN** failure 的 `recoverability` 必须为 `non_retryable`
- **AND** 所有非 PENDING 状态必须具有稳定 status reason

#### Scenario: 依赖失败导致跳过

- **WHEN** Task 因前置 Task 失败而不应执行
- **THEN** 状态为 `SKIPPED` 并记录稳定 reason
- **AND** completion 与 failure 均为空

### Requirement: Revision 必须区分合法演进与冲突

相同 Task ID、不可变内容一致、revision +1、合法状态边和时间不倒退时分类为 `same-task-next-revision`；相同快照为 identical；其余同 ID 合法内容为 conflicting；不同 ID 为 distinct。

### Requirement: Contract 必须严格版本化并隔离 ground truth

所有对象拒绝未知字段，不得包含期望动作、评分标签或 Evaluation ground truth。
