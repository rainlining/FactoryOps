# Change 提案：持久化 Coordinator Fusion

- `change_id`: `2026-08-19-persist-coordinator-fusion`
- `status`: `review-handoff-ready`
- `learning_level`: `delegated`
- `depends_on`: `2026-08-19-define-coordinator-fusion-contract`
- `feature_branch`: `codex/persist-coordinator-fusion`

## 动机与范围

Fusion Contract 已冻结，但结果仍无法可靠保存、重放和供后续 Risk Gate 查询。本 Change 在 Agent Service 用 MySQL 保存不可变 Fusion 事实及其 Recommendation 来源关联，提供稳定的 identical/conflicting 分类和读取完整性校验。

## 非目标

不生成 Fusion、不调用模型、不修改 Risk Contract、不运行 Risk/Approval、不完成 Coordinator Execution、不调用 Java Business API、不实现 HTTP/Evaluation，也不修改 `dataset/`。

## 学习等级

`delegated`。复用首次 deep 的 `2026-08-18-persist-specialist-recommendation` 及后续 Risk Persistence 的不可变事实、advisory admission、canonical hash 和父事实锁定模式。新增点是多个 Recommendation 来源的固定排序锁和关联表，没有新增所有权或失败模型。
