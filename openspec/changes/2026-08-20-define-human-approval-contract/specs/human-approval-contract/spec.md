# Human Approval Contract 规格增量

### Requirement: Approval 必须绑定真实待审批 Risk Decision

Approval 必须复制 decision/fusion/run identity 与 Gate provenance；公开校验边界必须逐字段比对完整 Risk Decision，且只接受 `REQUIRE_APPROVAL`。key 必须由 decision key 确定派生。

### Requirement: Approval 状态必须单向且具备明确 actor

revision 1 必须为 PENDING；只能进入 APPROVED、REJECTED 或 EXPIRED。批准/拒绝必须是 HUMAN 且决定时间严格早于 `expires_at`；从 `expires_at` 瞬间起只能由 SYSTEM 记为 EXPIRED。终态不得迁移，请求时间必须早于过期时间，决定时间不得早于请求时间。

### Requirement: Approval 不得伪造业务动作完成

Contract 只记录审批 Gate，不得包含 action executed、业务结果、ground truth 或未知字段。APPROVED 仍需后续 Java Business API 执行动作。

### Requirement: Approval 必须可确定性重放与分类

canonical 必须稳定并把 policy/reason 数组视为无序集合；相同快照为 identical，规范化后不可变区域相同的合法 revision+1 为 next revision，其余同 key 内容为 conflicting，不同 key 为 distinct。
