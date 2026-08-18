# 设计

Contract v1.0.0 使用共享 envelope：identity、recommendation、details、generated_at。identity 绑定 execution/run/task/role；`recommendation_key = SHA-256("v1\n<execution_id>")`，保证同一 attempt 只有一个稳定建议事实。公共 recommendation 只允许正式 V1 action、severity、有限 confidence、证据和 reason codes。

details 采用按 agent_role 条件约束的三种严格对象：Quality 保存 `consecutive_defect_suspected`；Production 保存 delay/downtime 和 order refs；SLA 保存非负成本、ISO 风格 currency 与至少一个正式动作成本。角色特定的详细解释或模型原文进入 Artifact Store，不直接膨胀 Contract。

Validator 顺序：版本 → finite/角色 preflight → Draft 2020-12 Schema → key → 唯一数组。`generated_at` 在本 Contract 只校验 UTC 形状；它与 Execution 生命周期的跨对象时间关系留给后续持久化层。Canonical JSON 排序键、压缩分隔符、整数浮点归一化、禁止 NaN。relation 只区分 identical/conflicting/distinct，不提供可变 revision。
