# Task Lease 规格增量

## ADDED Requirements

### Requirement: Claim 必须具备 owner、token 和 expiry

只有 PENDING Task 可被 claim；未过期 lease 阻止其他 owner，过期 lease 可安全接管。

### Requirement: Renew 和 Release 必须验证 ownership

renew/release 必须同时匹配 task、owner、token；过期或陈旧 token 不得续租或删除新 lease。

### Requirement: Lease 不得伪造执行状态

claim、renew、release 不改变 Task status/revision，也不创建 Agent Execution。
