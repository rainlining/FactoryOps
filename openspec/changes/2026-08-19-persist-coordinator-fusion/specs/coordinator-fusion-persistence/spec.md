# Coordinator Fusion Persistence 规格增量

### Requirement: Fusion 必须原子绑定真实来源

首次保存必须在同一事务校验 RUNNING Coordinator Execution 与全部 Specialist Recommendation 来源；任一缺失、损坏或错配不得留下主事实或关联事实。

### Requirement: Fusion 必须不可变且并发幂等

相同 key/ID 的并发 identical/conflicting 保存必须稳定分类且只保留一个赢家；同 key 不同 ID 或同 ID 不同 key 不得形成身份分裂。

### Requirement: 读取必须验证完整性

读取必须重新验证 canonical hash、Contract、typed columns、来源 payload 与关联集合，损坏数据不得作为可信 Fusion 返回。
