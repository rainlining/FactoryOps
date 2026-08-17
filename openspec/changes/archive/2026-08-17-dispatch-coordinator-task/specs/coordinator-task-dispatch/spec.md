# Coordinator Task Dispatch 规格增量

## ADDED Requirements

### Requirement: 只有运行中的 Coordinator 才能创建 Task

dispatch 必须锁定并验证 `agent_executions` 为 Coordinator、RUNNING，且 Execution 与目标 Run 相同；否则不得写 Task。

### Requirement: Task 创建必须原子且幂等

同一事务必须写入 PENDING Task、依赖 junction 和 revision 0 初始 history。相同 `task_request_id` 与 payload 重放返回 identical，不同 payload 返回 conflicting。

### Requirement: Task 输入和依赖必须遵守 Contract

task type/role、优先级、Context/evidence 引用和依赖必须通过 Task Validator；依赖必须存在且属于同一 Run。

### Requirement: 失败不得留下半成品

任一 Task history、依赖或审计写入失败时，Task 与其所有本次事实必须回滚。
