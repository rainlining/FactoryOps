# Specialist Recommendation Contract 规格增量

## ADDED Requirements

### Requirement: Specialist 输出必须严格版本化并绑定 Execution

每份 Recommendation 必须属于一个 Quality、Production 或 SLA Execution，并携带稳定 recommendation ID/key、Run、Task 和 generated_at。key 必须由 contract version 与 execution ID 确定性生成。

### Requirement: 公共建议字段必须结构化

输出必须包含正式 V1 action、severity、[0,1] 有限 confidence、唯一 evidence refs、唯一 reason codes 和 details；不得传递自由聊天历史或模型原文。

### Requirement: details 必须匹配角色

Quality 只能输出质量 details；Production 必须输出 delay/downtime/affected orders；SLA 必须输出 expected cost、currency 和按动作区分的 alternative costs。角色与 details 不匹配必须拒绝。

### Requirement: Canonical 与 duplicate 分类必须稳定

键顺序和整数浮点表示不得改变 canonical bytes；同 key/相同 canonical 为 identical，同 key/不同内容为 conflicting，不同 key 为 distinct。

### Requirement: Evaluation ground truth 必须隔离

未知字段、ground_truth、expected_action、score label、NaN 和 Infinity 必须在进入 Agent Runtime 后续边界前拒绝，并返回可定位错误。
