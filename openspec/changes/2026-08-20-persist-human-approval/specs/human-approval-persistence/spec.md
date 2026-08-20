# Human Approval Persistence 规格增量

### Requirement: Approval 必须原子绑定真实 Risk provenance

保存必须在同一事务锁定并完整验证 `REQUIRE_APPROVAL` Risk Decision 及其 Fusion provenance，再写 current/history；失败不得留下半事实。

### Requirement: Approval revision 必须可审计且并发安全

revision 1 与合法 revision 2 必须追加 history；current 只指向最高 revision。并发 identical 稳定 replay，并发相反终态只能一个成功，输家 conflicting，不得泄漏数据库异常。

### Requirement: Approval identity 与读取必须防损坏

key/ID split 必须拒绝；读取必须重验 canonical hash、typed columns、Risk binding 和完整 history，损坏不得作为可信审批返回。

### Requirement: Approval persistence 不得执行副作用

保存和读取不得推进 Run/Execution、修改 Risk/Fusion 或调用业务动作。
