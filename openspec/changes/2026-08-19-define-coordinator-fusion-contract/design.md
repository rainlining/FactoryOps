# 设计：Coordinator Fusion Contract

Fusion payload 绑定一个 Run、Coordinator Execution 和正整数 round，引用已持久化的 Specialist Recommendation identities；输入引用必须唯一、角色最多各一个，present roles 与 missing roles 必须恰好覆盖 Quality/Production/SLA。输出只生成显式 rank 的候选动作，不宣称已授权或已执行。

确定性规则：`fusion_key = SHA-256("v1\n<run_id>\n<coordinator_execution_id>\n<round>")`；candidate rank 必须从 1 连续递增，rank 1 等于 proposed action。相同输入 canonical identical，不同输入 conflicting；recommendation refs、support/opposition roles、evidence 和 reason codes 保留 provenance。`authorization_state` 固定为 `NOT_EVALUATED`。

公开 validator 同时接收源 Recommendation payloads，逐项比对 ID/key/execution/task/role/action/severity/confidence，并验证所有输入属于同一 Run。测试覆盖角色重复、跨 Run、Coordinator Execution key 错配、角色覆盖、rank、ground-truth/模型原文泄漏、canonical 数字规范化和关系分类。
