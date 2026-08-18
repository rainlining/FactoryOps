# Change 提案：定义 Specialist Recommendation Contract

- `change_id`: `2026-08-18-define-specialist-recommendation-contract`
- `status`: `review-handoff-ready`
- `learning_level`: `deep`
- `depends_on`: `2026-08-18-retry-worker-task-execution`
- `feature_branch`: `codex/define-specialist-recommendation-contract`

## 动机与范围

Worker 已能管理 Execution attempt，但 Quality、Production、SLA Agent 尚无版本化结构化输出，Model 结果无法可靠校验、重放、融合或评测。本 Change 冻结 v1.0.0 Specialist Recommendation Contract、严格 Validator、canonical form 与 duplicate relation classifier。

## 非目标

不定义 Risk Gate 或最终 Decision，不调用模型/Tool，不组装 Prompt/Context，不持久化 Recommendation，不完成 Worker Execution，不实现 Coordinator Fusion、Java API、Evaluation，也不修改 `dataset/`。

## 学习等级

`deep`。这是首次冻结 LLM 结构化输出协议，新增角色分支、有限数值、规范化、幂等身份和 ground-truth 隔离边界。
