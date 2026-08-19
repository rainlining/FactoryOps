# Change 提案：定义 Risk Decision Contract

- `change_id`: `2026-08-19-define-risk-decision-contract`
- `status`: `review-handoff-ready`
- `learning_level`: `deep`
- `depends_on`: `2026-08-18-persist-specialist-recommendation`
- `feature_branch`: `codex/define-risk-decision-contract`

## 动机与范围

Recommendation 只能表达专业建议，尚无独立 Risk/Policy Gate 决定建议是否允许进入业务执行。本 Change 冻结 Risk Decision v1.0.0：结构化风险等级、allowed action、approval requirement、policy refs 和 recommendation identity binding。

## 非目标

不执行动作，不调用 Java API，不创建 Approval 记录，不融合 Recommendation，不调用 Model/Tool，不持久化、不实现 HTTP/Evaluation，也不修改 `dataset/`。

## 学习等级

`deep`。首次冻结权限/审批边界和高风险动作不变量；复用 Recommendation Contract 的 strict schema、canonical、key 和 ground-truth 隔离模式。
