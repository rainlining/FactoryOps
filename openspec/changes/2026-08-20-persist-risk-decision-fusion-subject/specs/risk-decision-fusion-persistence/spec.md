# Risk Decision Fusion Persistence 规格增量

### Requirement: 双 Subject 必须原子保存

Recommendation/Fusion Risk Decision 必须在同一事务校验对应来源、写入一个不可变事实，并稳定支持 identical/conflicting replay。

### Requirement: 读取必须验证 Subject 完整性

读取必须重新校验 discriminator、typed columns、canonical hash、payload Contract 和来源事实；来源缺失、错配或损坏必须拒绝。
