# Human Approval Run Pause

## 新增需求

### Requirement: PENDING Approval 与 Run wait 必须原子提交

首次持久化合法 PENDING Human Approval 时，系统必须在同一 Agent MySQL 事务内把来源 Run 从 RUNNING 推进到 WAITING_FOR_APPROVAL，并写入不可变 transition history；任一步失败不得留下半完成事实。

#### Scenario: transition 写入失败

- **When** Approval current/history 已计划写入，但 wait transition insert 失败
- **Then** Approval 行为 0，Run 仍为 RUNNING，wait transition 为 0

### Requirement: wait transition 必须以 Approval 确定性幂等

transition request ID 必须由 Approval ID 确定性派生。相同 canonical Approval 重放只能返回 identical，并要求 wait transition 及其到 Run current 的后续 transition 构成连续合法历史，current summary 必须与最新 transition 一致；Run 合法恢复后不得因此破坏历史 Approval 可读性。不同 payload 或不同 transition fact 不得覆盖已有状态。

#### Scenario: 并发相同 Approval

- **When** 两个调用并发保存同一 PENDING Approval
- **Then** 一个 applied、一个 duplicate-identical，只有一条 Approval current/history 与一条 Run wait transition

### Requirement: 仅 RUNNING Run 可进入审批等待

首次 Approval 不得把 PENDING、SUSPENDED、终态或已由无关原因等待的 Run 改写为 WAITING_FOR_APPROVAL。Terminal Approval 保存不得在本 Change 恢复或完成 Run。

#### Scenario: 来源 Run 已终态

- **When** 合法 Approval 指向 SUCCEEDED/FAILED/CANCELLED Run
- **Then** 保存 fail closed，Approval 与 transition 均不落库
