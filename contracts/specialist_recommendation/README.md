# Specialist Recommendation Contract v1.0.0

本 Contract 是 Quality、Production、SLA Agent 的严格结构化建议输出。它绑定一次 Specialist Execution attempt，不是最终 Decision，也不授权执行任何业务动作。

`recommendation_key` 对 UTF-8 文本 `v1\n<execution_id>` 计算 SHA-256 并添加 `RCK-`。Retry 创建新的 Execution，因此必须创建新的 Recommendation，不能覆盖旧 attempt。

公共 action 只允许 V1 正式动作：`PASS`、`RECHECK`、`REJECT_ITEM`、`HOLD_BATCH`、`STOP_LINE`、`ESCALATE`。角色专属 details 不允许任意字段。模型原文、长解释和大对象使用 `output_artifact_refs`。

Validator 显式拒绝 NaN/Infinity、重复引用、key 不一致、角色 details 不匹配、未知字段和 Evaluation ground truth。relation classifier 区分 identical、conflicting 和 distinct。
