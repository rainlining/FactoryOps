# 设计：Approval Action Target Binding

Human Approval v1.1.0 仅增加 `identity.incident_id`，格式沿用 Quality Incident ID。Approval key/ID 仍由 decision key 派生，因为一个 Risk Decision 只能产生一个审批；incident 是该审批不可变 provenance，不是新的幂等维度。

Contract validator 同时支持 v1.0.0 legacy 与 v1.1.0。v1.0 保持原两参数调用；v1.1 必须提供 source Run，并验证 approval identity 的 `run_id`、`incident_id` 分别等于 Risk Decision 和 Run provenance，且 Run identity 等于 Risk 的 run。canonical/relation 对两个版本分别稳定工作，禁止跨版本 next revision。

Agent migration 015 给 current 表增加 nullable `incident_id`：legacy v1.0 行保持 NULL，新 v1.1 保存必须非空。保存事务沿既有 Fusion provenance → Risk → Approval 锁序，在 Risk 后、Approval 前锁定对应 Run并重验 incident；读取 v1.1 同样重验 typed incident 与 Run provenance。history 的 canonical payload已经包含 incident，无需新增重复列。

Java V7 给 `business_approvals` 增加 nullable `incident_id` 并打包 v1.1 schema。internal create 从本 Change 起只接受 v1.1；读取仍支持既有 v1.0。所有 current typed projection 和 history 继续 fail closed。后续动作执行必须只从审批的 incident 解析业务目标，不接受自由 target。

选择该方案而不是贯穿 Specialist/Fusion/Risk 添加 target：动作目标来自不可变 Run 根 provenance，而不是模型建议；把它写入模型 Contract 会扩大 LLM 输入/输出责任。也不选择执行时临时按 run 查询，因为那会让审批审计快照缺失目标。
