# Risk Decision Contract 规格增量

## ADDED Requirements

### Requirement: Risk Decision 必须绑定 Recommendation

每份 Risk Decision 必须绑定 recommendation_id/key、run/task 和生成时间；接收边界必须向 validator 提供源 Recommendation identity 并逐字段比对，binding 不一致必须拒绝。

### Requirement: 高风险动作必须要求审批

`STOP_LINE` 必须为 `HIGH` risk 且 `approval_required=true`；`PASS`/`RECHECK` 不得伪造高风险等级。

### Requirement: Policy 结果必须结构化

输出必须包含 `decision`（ALLOW/BLOCK/REQUIRE_APPROVAL）、risk_level、allowed_actions、policy_refs 和 reason_codes；数组唯一且不得包含 ground truth。

`ALLOW` 必须把 proposed action 列入 `allowed_actions`；`BLOCK` 和 `REQUIRE_APPROVAL` 必须排除 proposed action，避免把阻止或待审批动作同时表达为已授权。

### Requirement: Contract 必须严格版本化、可规范化和幂等分类

未知字段、NaN/Infinity、非法动作和空 policy refs 必须拒绝；canonical 必须归一化整数与等值整数浮点，相同 decision key canonical identical，不同内容 conflicting，不同 key distinct。
