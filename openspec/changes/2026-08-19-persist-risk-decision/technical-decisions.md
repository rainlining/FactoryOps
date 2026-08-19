# 技术选型

- Risk Decision 是 Recommendation 的不可变子事实，不是 Approval 或执行结果。
- 父 Recommendation 行在事务内 `FOR UPDATE` 并执行完整 integrity decode，不能只信任 FK/查询列。
- 同时对 decision key 与 decision ID 获取排序 advisory locks，覆盖两个唯一身份维度的并发冲突。
- payload 保存 canonical JSON 与 SHA-256，同时保存 decision/risk/action 等查询列；读取双向核对。
- 不复用 Agent Task/Execution lock，因为本 Change 不推进其状态，也不定义 Risk Worker 生命周期。
