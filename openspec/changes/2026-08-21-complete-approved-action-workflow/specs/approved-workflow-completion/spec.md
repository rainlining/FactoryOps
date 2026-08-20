# Approved Workflow Completion 规格增量

## ADDED Requirements

### Requirement: 只有完整且 ready 的已批准 Workflow 可以成功完成

系统必须验证 terminal APPROVED HOLD_BATCH、Java execution receipt、Fusion/Risk/Approval provenance、已恢复的 Run、RUNNING Coordinator Execution，以及至少两个且全部 SUCCEEDED 的 Specialist Task。任何缺失、漂移或未完成不得产生成功副作用。

#### Scenario: Task 尚未完成

- **WHEN** 任一来源 Run Task 不是 SUCCEEDED
- **THEN** Coordinator Execution 与 Run 保持原状态

### Requirement: Coordinator Execution 与 Run 必须原子成功

系统必须在一个 Agent MySQL 事务中写入 Coordinator Execution `RUNNING → SUCCEEDED` result/history 与 Run `RUNNING → SUCCEEDED` history；任一写入失败必须全部回滚。

#### Scenario: 成功完成

- **WHEN** 完整 ready workflow 被完成
- **THEN** Coordinator Execution 和 Run 同时为 SUCCEEDED
- **AND** Coordinator result 通过 artifact/evidence refs 绑定 Fusion、Risk Decision 与 Approval provenance

### Requirement: 完成必须确定性幂等且 fail closed

相同 Approval completion 重放必须返回 identical 且不新增 history；并发相同调用只允许一个 applied。单边 transition、identity split、current/history 漂移或 conflicting replay 必须显式拒绝，不得修补或覆盖历史。
