# Human Approval Application 增量规格

## Requirement: Java owns approval decisions

Business Backend 必须接收已验证的 Human Approval v1.0.0 PENDING fact，持久化 current/history，并提供按 approval key 查询。Agent 不得直接声明或执行批准结果。

### Scenario: create and identical replay

首次创建返回 created；相同 canonical fact 重放返回 replay 且不重复 history；相同 key/ID 的不同事实或 key/ID split 返回 conflict。

## Requirement: fail-closed actor authorization

决定 API 必须从服务端 allowlist 解析 actor，未配置或未知 actor 必须返回 forbidden；客户端不得提交角色来提升自身权限。

### Scenario: unauthorized caller

未知 actor 请求批准时，状态保持 PENDING，history 不增加。

## Requirement: one terminal winner

系统必须在单事务行锁下执行 PENDING → APPROVED/REJECTED，写 current 与不可变 revision 2。相同终态命令重放返回 replay；不同终态或 actor/provenance 返回 conflict。

### Scenario: concurrent opposite decisions

并发 APPROVED 与 REJECTED 只能有一个 applied；输家稳定 conflict，current 与 revision 2 必须属于赢家。

## Requirement: expiry boundary

人工决定必须满足 `decided_at < expires_at`。到期或恰好边界必须拒绝且不改变 PENDING；本 Change 不通过读取触发 EXPIRED。

## Requirement: no business action side effect

审批 API 不得修改 Batch/Inspection/Incident，也不得执行候选动作或推进 Agent Run。
