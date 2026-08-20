# Change 提案：生成 Coordinator Fusion

- `change_id`: `2026-08-20-generate-coordinator-fusion`
- `status`: `review-handoff-ready`
- `learning_level`: `standard`
- `depends_on`: `2026-08-20-generate-specialist-recommendation`
- `feature_branch`: `codex/generate-coordinator-fusion`

Specialist Recommendation 已能由真实 Worker Execution 生成并持久化，但 Coordinator Fusion 仍只能由测试直接构造。本 Change 新增 Fusion 生成编排：调用方显式提交 2～3 个 Recommendation key，服务读取完整可信来源与 Coordinator Execution，调用受 provenance 约束的 provider 产生不可信 draft，由应用层控制 Fusion identity、输入引用、round、generated_at 与 `NOT_EVALUATED`，最后交给既有 persistence 原子保存。

非目标：不执行 Risk/Approval/Business Action，不完成 Coordinator Execution/Run，不自动选择“最新”Recommendation，不调用真实模型，不实现 HTTP/Kafka/Checkpoint/Artifact Store，不修改 Fusion Contract/schema 或 `dataset/`。

学习等级为 `standard`：provider 外调、provenance、replay 与保存期 fencing 复用首次 deep 的 Specialist Generation 模式；新增点是多来源集合、显式 round 与候选排序，但不引入新的副作用权限。
