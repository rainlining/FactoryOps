# Verification

状态：`applying`。

## TDD 与局部证据

- 初始 RED：模块缺失，测试 collection fail；首轮 GREEN 又实际暴露 Run counters 从未维护及 Execution Contract 不接受 `RSK-*` decision ID。
- 取舍：以锁定的 Task/Execution 集合作为 readiness 真值，在终态校准 Run counters；Risk 用 evidence ref 绑定，`decision_id` 保持 null，不伪造 `DEC-*`。
- 局部真实 MySQL：completion 单测 `6 passed in 19.85s`。
- 相关 Approval/resume/worker completion 联合：`43 passed in 80.90s`。
- 覆盖成功、相同重放、并发 identical、未完成 Task、双聚合中点失败回滚、transition identity split。
