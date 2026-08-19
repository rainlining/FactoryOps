# Change 提案：持久化 Risk Decision

- `change_id`: `2026-08-19-persist-risk-decision`
- `status`: `applying`
- `learning_level`: `delegated`
- `depends_on`: `2026-08-19-define-risk-decision-contract`
- `feature_branch`: `codex/persist-risk-decision`

## 动机与范围

Risk Decision Contract 已冻结，但 Gate 输出尚不能成为可重放、可审计的事实。本 Change 新增 migration 011 与持久化 Service：锁定并验证源 Specialist Recommendation，逐字段验证 Risk binding，原子保存 canonical payload、hash 和查询列，并稳定分类 identical/conflicting。

## 非目标

不运行 Risk Agent，不调用 Model/Tool，不创建 Approval，不执行 Java Business Action，不推进 Task/Execution，不做 Coordinator Fusion、HTTP、Evaluation，也不修改 `dataset/`。

## 学习等级

`delegated`。复用 `2026-08-18-persist-specialist-recommendation` 的 immutable canonical fact、advisory admission、typed-column integrity 和 replay 分类模式；新增点仅是 Recommendation 父事实校验及双 identity lock，没有新的状态机、lease ownership 或业务副作用。
