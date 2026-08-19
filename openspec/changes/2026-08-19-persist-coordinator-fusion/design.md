# 设计：持久化 Coordinator Fusion

`CoordinatorFusionService.save` 先 canonicalize，再按 fusion key/ID 的摘要名称排序取得 MySQL advisory locks。首次写入在一个事务内锁定 RUNNING Coordinator Execution，再按 Recommendation key 排序锁定 2～3 个来源事实，调用公开 Fusion validator 比对所有引用，最后写主事实与关联表。

已有事实优先分类，因此父 Execution 后续结束仍可稳定 replay。读取重新校验 canonical hash、Contract、typed columns、来源 payload 与关联集合。锁超时、父事实缺失/损坏、来源错配、identity split 或唯一约束无可读赢家都失败且不留部分事实。

不修改 Execution、Task、lease、Recommendation 或 Risk Decision。
