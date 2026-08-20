# Approval Action Target Binding Design

本设计以 Human Approval v1.1 将 `incident_id` 固化到审批 identity。Risk Decision 已绑定 Run，Run 已绑定 Quality Incident；Agent persistence 在同一事务锁定并验证这条链。Java 只接受 v1.1 新审批并保存 incident typed projection，legacy v1.0 只读兼容。后续 Business Action 从 incident 解析目标，不接受调用者自由指定 target。

范围只覆盖 Approval Contract、Agent Approval persistence 和 Java Approval API；不修改模型输出 Contract、不执行动作、不发布事件。
