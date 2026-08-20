# Fusion Risk Evaluation 规格增量

### Requirement: Risk Gate 必须只评估可信 Fusion

评估服务必须按 fusion key 读取并完整验证持久化 Fusion；缺失、Contract/provenance/hash 损坏均必须拒绝，且不得创建 Risk Decision。

### Requirement: v1 风险策略必须确定且保守

PASS/RECHECK 必须为 LOW/ALLOW；无冲突的 REJECT_ITEM/HOLD_BATCH 必须为 MEDIUM/ALLOW，有冲突时必须 REQUIRE_APPROVAL；STOP_LINE 必须为 HIGH/REQUIRE_APPROVAL。ESCALATE 是进入人工流程的路由动作，必须为 LOW/ALLOW，避免循环审批。REQUIRE_APPROVAL 不得表述为已授权或已执行。

### Requirement: 评估必须产生可重放的 Fusion Risk Decision

输出必须是绑定完整 Fusion identity 的 Risk Decision v1.1；key 与 ID 必须由 Fusion key 确定派生，confidence 必须来自 rank 1 candidate score，policy/reason 必须版本化。相同 command 的顺序或并发 replay 必须只保留一个 Decision 并稳定分类 identical；冲突内容不得覆盖历史。

### Requirement: Risk Gate 不得产生业务副作用

评估和保存不得推进 Run、Task、Execution，不得执行 Approval 或 Java Business Action。
