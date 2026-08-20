# Approved Action Resume

## 新增需求

### Requirement: 只有真实执行回执才能恢复 Run

系统必须先持久化合法 APPROVED terminal Approval，再调用 Java approval-keyed execute API。只有回执与 Approval key/action/incident 一致且状态为 EXECUTED，来源 Run 才能从 WAITING_FOR_APPROVAL 恢复 RUNNING。

#### Scenario: 回执 target 不匹配

- **When** Java 响应的 incident/action/approval key 与 Approval 不一致
- **Then** Agent fail closed，Run 保持 WAITING，不写 resume transition

### Requirement: 跨库 crash window 必须可重放恢复

系统不得声称 Java DB 与 Agent DB 原子提交。Java 已执行而 Agent resume 未提交时，相同 terminal Approval 重试必须接受 Java replay，并以确定性 transition request ID 完成一次 Run resume。

#### Scenario: Java 成功后 Agent DB 失败

- **Given** Java 已持久化 EXECUTED receipt
- **When** Agent resume transaction 失败后相同请求重试
- **Then** Java 返回 replay，Agent 只写一条 WAITING→RUNNING transition，业务动作不重复

### Requirement: HTTP 失败不得无条件自动重试

网络、timeout、非 2xx 与 malformed response 必须转为稳定错误并保持 Run WAITING；本服务不得在单次调用内无限或无条件 retry。

#### Scenario: Java 返回 409/500

- **When** execute endpoint 返回非 2xx
- **Then** 当前调用失败，Run 和 resume history 不变，调用者可依据上层策略显式重试
