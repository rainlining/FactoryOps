# Change 提案：扩展 Risk Decision 的 Fusion Subject

- `change_id`: `2026-08-19-extend-risk-decision-fusion-subject`
- `status`: `review-handoff-ready`
- `learning_level`: `delegated`
- `depends_on`: `2026-08-19-persist-coordinator-fusion`
- `feature_branch`: `codex/extend-risk-decision-fusion-subject`

## 动机与范围

Coordinator Fusion 已成为多 Specialist 的候选汇总事实，但现有 Risk Decision v1.0 只能绑定单个 Recommendation，无法表达 `Fusion → Risk Gate` 的架构顺序。本 Change 发布 Risk Decision v1.1 subject binding：Risk Decision 可以绑定一个持久化 Fusion，并保留 Fusion 的 run、Coordinator Execution 和 round provenance。

## 非目标

不实现 Risk Agent、模型调用、Risk Decision 持久化迁移、Approval、Java Business API、业务动作、HTTP/Evaluation，也不修改 `dataset/`。

## 学习等级

`delegated`。复用 Risk Decision Contract 首次 deep Change 与 Fusion Contract 的版本化、canonical 和 provenance 模式；新增点仅是互斥 subject binding 和 Fusion identity 比对，不引入新事务或并发语义。
