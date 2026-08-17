# Agent Execution Lifecycle Persistence 规格增量

## ADDED Requirements

### Requirement: Execution 创建必须幂等且原子

系统必须按 Contract `execution_key` 唯一创建 PENDING snapshot 与 revision 0 history。

#### Scenario: 首次与重复创建
- **WHEN** 合法创建首次提交、相同重投或冲突重投
- **THEN** 分别返回 applied、duplicate-identical 或 duplicate-conflicting，且只存在一个 snapshot/history

#### Scenario: 初始历史失败
- **WHEN** history 写入失败
- **THEN** snapshot 必须回滚

### Requirement: 父对象与角色必须一致

Coordinator Execution 必须引用存在的 Run 且 task_id 为空；Specialist 必须引用同 Run、目标 role 匹配的 Task。

#### Scenario: 缺失或不匹配父对象
- **WHEN** Run/Task 不存在、Task 属于另一 Run 或 role 不匹配
- **THEN** 拒绝创建且无部分数据

### Requirement: 生命周期迁移必须受幂等和乐观锁保护

系统必须按 transition_request_id 幂等，并以 execution_id + expected status + expected revision 条件更新 snapshot 与追加 history。

#### Scenario: 重投与并发
- **WHEN** 相同 request 重投、冲突重投或不同 request 竞争 revision
- **THEN** 分别分类 identical、conflicting，且竞争最多一个 applied

#### Scenario: history 失败
- **WHEN** 条件更新后 history 插入失败
- **THEN** snapshot 更新回滚

### Requirement: 状态、结果、失败与时间必须满足 Contract

系统必须支持 PENDING→RUNNING/CANCELLED、RUNNING→SUCCEEDED/FAILED/CANCELLED，保护终态、时间单调和 result/failure 互斥。

#### Scenario: 成功、失败与取消
- **WHEN** 迁移到终态
- **THEN** SUCCEEDED 只保存 result、FAILED 只保存 failure、CANCELLED 两者均为空

### Requirement: Execution 引用必须具有数据库完整性

Execution 必须 FK 到 Run/Task；Run coordinator 与 Task creator/current/completion/failure 引用必须 FK 到 Execution，删除均为 RESTRICT。

#### Scenario: 孤立引用
- **WHEN** 写入或升级遇到不存在的 Execution 引用
- **THEN** 数据库拒绝操作

### Requirement: 读取必须重建严格 Contract

读取必须从结构化列重建 v1.0.0 Contract 并调用 `validate_execution`；非法数据必须抛持久化完整性错误。
