# 技术选型

## 选择双聚合单事务收口

Coordinator Execution 与 Run 同在 Agent MySQL，使用一个本地事务比串行调用两个 lifecycle service 更可靠；后者在中间崩溃时会产生 Execution 已成功但 Run 仍运行的半完成状态。

## 选择复用 resume saga

completion 不复制 Java action 调用，也不相信调用者声称“动作已执行”。它先调用上一 Change 的 resume service，取得并验证真实/重放 receipt，再做纯 Agent 收口。跨库仍不使用 2PC，恢复依赖 Java receipt 与 Agent transition 的双幂等锚点。

## 不引入 completion receipt 表

两个确定派生的 transition request ID 已分别唯一约束 Execution 与 Run completion，且二者在同事务写入；额外 receipt 表不会增加可恢复性，只会扩大 migration 与一致性表面。

## 终态校准 Run progress counters

RED 测试确认现有 dispatch/worker completion 没有维护 Run 的两个 Task counter。为避免扩大到重写两个既有服务，本 Change 在锁定全部 Task 且确认均成功后，以实际集合校准终态 Run counters。运行中 counter 实时维护列为后续可观测性改进，不影响本 Change 的 readiness 真值来源。
