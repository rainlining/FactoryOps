# Change 提案：生成 Specialist Recommendation

- `change_id`: `2026-08-20-generate-specialist-recommendation`
- `status`: `review-handoff-ready`
- `learning_level`: `deep`
- `depends_on`: `2026-08-20-evaluate-fusion-risk-decision`
- `feature_branch`: `codex/generate-specialist-recommendation`

当前 Worker Execution 可以启动，Recommendation Contract 与 persistence 也已具备，但运行时仍由测试直接构造完整 Recommendation。本 Change 新增生成编排：从真实 RUNNING Specialist Execution/Task 建立最小上下文，调用与 Execution 冻结 provenance 绑定的可替换 provider 取得不可信 draft，由应用层控制身份与生成时间、限制 evidence/artifact 引用，再交给既有 persistence 原子保存并重验 parent/context/provenance fencing。

同时提供内存 recorded provider，供可复现演示与后续端到端 Workflow 使用；真实 LLM/Prompt/Context Assembly 将通过相同 provider 协议在后续 Change 接入。

非目标：不调用真实模型，不读取 Evaluation ground truth，不完成 Worker Execution/Task，不生成 Fusion/Risk，不实现 Kafka/HTTP/Approval/Java Business Action，不修改 Recommendation Contract/schema 或 `dataset/`。

学习等级为 `deep`：这是首次冻结 Model/Agent provider 的信任边界、调用失败语义和“外部调用不持有数据库事务”的并发模型。Owner Review/Learning 延后至成品可展示后；此前不得归档或合并 main。
