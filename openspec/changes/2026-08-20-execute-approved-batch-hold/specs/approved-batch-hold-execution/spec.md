# Approved Batch Hold Execution

## 新增需求

### Requirement: 目标只能由已批准事实解析

执行入口不得接受 Batch/Line；系统必须从 APPROVED Human Approval v1.1 的 incident 解析唯一 Quality Incident 与 Batch，并重验 Approval current/history 完整性。

#### Scenario: 调用者尝试指定目标

- **When** 调用执行入口并附加 body target
- **Then** 请求必须拒绝或忽略整个 body，且不得按该 target 执行

### Requirement: HOLD_BATCH 原子且幂等

首次执行必须在一个事务内把目标 Batch 从 OPEN 变为 HELD 并写一条 approval-keyed EXECUTED receipt；相同 Approval 重放不得重复副作用。receipt 必须同时绑定 Approval ID 与 Key；任一 identity 分裂、多行命中或 typed 状态漂移必须作为完整性错误拒绝，不得依靠数据库唯一键异常分类。

#### Scenario: 并发相同执行

- **When** 两个线程同时执行同一 APPROVED HOLD_BATCH
- **Then** 一个 applied、一个 replay，只有一条 receipt，Batch 只冻结一次

### Requirement: 权限与失败路径 fail closed

PENDING、REJECTED、非 HOLD_BATCH、未知/漂移 incident、冲突 Batch 或 receipt corruption 必须拒绝；事务失败不得留下半完成 Batch/receipt。

#### Scenario: receipt 写入失败

- **When** Batch hold 后 receipt insert 在同事务失败
- **Then** Batch 仍为 OPEN，receipt 为 0
