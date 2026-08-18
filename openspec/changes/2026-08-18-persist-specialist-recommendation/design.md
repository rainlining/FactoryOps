# 设计

入口 `SpecialistRecommendationService.save` 先执行 Contract Validator/canonicalize，再取得 `recommendation-key` named advisory lock。事务内先查 key 或 ID；已有事实按 canonical SHA/bytes 分类。首次保存按 Task→Execution 固定顺序加行锁，与 Worker Completion 的共享对象相对锁序一致；校验 RUNNING/current pair 与 run/task/role 后插入 typed columns、canonical LONGTEXT 和 SHA-256。finally 释放 advisory lock。

读取按 key/ID 解析 canonical JSON、重新 validate，并校验存储 hash 和查询列一致；任何偏差抛持久化完整性错误。Recommendation 是 immutable fact，没有 revision。已保存事实的重放优先于父对象当前状态，因此 Completion 后仍能 identical replay。

推荐 ID 由 Contract 调用方提供，key 由 Execution 确定性派生。key 与 execution_id 均唯一；recommendation_id 主键冲突在 admission 后重读 ID 并稳定分类，不把 IntegrityError 暴露给调用方。
