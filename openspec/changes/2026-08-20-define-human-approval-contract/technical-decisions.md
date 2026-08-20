# 技术选型

- 使用 snapshot + revision，而不是事件数组：复用 Run/Task/Execution Contract 模式，持久化层后续可用乐观并发控制。
- 一个 Risk Decision 一个 approval key：避免同一高风险动作并发产生两个相互矛盾的审批流。
- actor 只保存 `actor_type` 与稳定 `actor_id`，不保存姓名等展示 PII。
- EXPIRED 使用 SYSTEM actor，避免伪造人工拒绝；APPROVED/REJECTED 只接受 HUMAN。
- Approval 不包含 `action_executed`：业务副作用必须由后续 Java Business API 独立审计。
