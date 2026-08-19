# Risk Decision Persistence 规格增量

## ADDED Requirements

### Requirement: 保存必须绑定完整且可信的 Recommendation 事实

系统必须锁定并完整校验源 Recommendation 的 canonical hash、Contract 与 typed columns，再逐字段比对 Risk Decision 的 recommendation ID/key、Run 和 Task；缺失、损坏或错配必须拒绝且无写入。

### Requirement: Risk Decision 必须保存为不可变 canonical 事实

系统必须保存严格 Contract canonical JSON、SHA-256 和 Gate 查询列；读取必须重新验证源 Recommendation、Risk Contract、hash 和 typed columns，损坏数据不得尽力返回。

### Requirement: 保存必须在两个身份维度并发幂等

相同 decision key 与 canonical payload 返回 identical；相同 key 不同 payload或同 decision ID 不同 key返回 conflicting。并发只能留下一个事实，不得泄漏数据库异常。

### Requirement: 持久化不得产生业务副作用

保存 Risk Decision 不得修改 Recommendation、Execution、Task 或 lease，不得创建 Approval 或调用 Business API。
