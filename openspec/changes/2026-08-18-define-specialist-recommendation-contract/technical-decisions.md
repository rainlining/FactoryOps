# 技术选型

- 不把三类输出拆成三个 Contract：共享融合语义和 identity 更重要，角色 details 由严格条件分支保持类型安全。
- 不加入 Risk：Risk 是权限/审批 Gate，不是并行专业建议，后续独立 Contract。
- 不允许任意 metrics map：它会绕过版本治理；v1 只冻结顶层规格已明确的最小角色字段。
- 金额使用 JSON number 只作建议估算；真实业务金额和币种精度由 Java Business API 决定，本 Contract 不产生账务副作用。
- 推荐 key 绑定 Execution attempt，而不是 Task；retry 的新 Execution 必须产生新建议，不能覆盖失败 attempt 历史。
