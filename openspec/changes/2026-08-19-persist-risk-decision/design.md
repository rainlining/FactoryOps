# 设计：持久化 Risk Decision

`RiskDecisionService.save` 先对 payload 做 canonical 结构校验，再按 decision key 与 decision ID 的摘要名称排序获取两个 MySQL advisory locks。事务内锁定源 `specialist_recommendations` 行、校验其 hash/Contract/typed columns，调用公开 Risk validator 比对 recommendation ID/key、Run、Task，最后插入 `risk_decisions`。重放必须读取并重新校验源 Recommendation 与 Risk payload。

表保存 decision/recommendation identity、Gate 查询列、canonical SHA-256、payload JSON 与时间。Recommendation ID、decision key、decision ID 都唯一；父 Recommendation 使用 FK RESTRICT。保存不修改 Recommendation、Execution、Task 或 lease。

双 advisory lock 解决相同 key/不同 ID 与相同 ID/不同 key 的并发竞争；锁名排序保持固定获取顺序。IntegrityError 仅作为数据库唯一约束的最后恢复路径，恢复时必须能读到唯一赢家，否则抛完整性错误。

失败路径：父 Recommendation 缺失/损坏、binding mismatch、Contract 非法、admission timeout、唯一身份分裂和存储 hash/typed columns 损坏。任一失败都不得留下部分事实。

测试使用真实 MySQL 覆盖首次保存、终态父对象后 replay、缺失/错配、identical/conflicting 并发、同 ID 跨 Recommendation、hash/typed corruption 和状态不推进。
