# Change 提案：定义 Coordinator Fusion Contract

- `change_id`: `2026-08-19-define-coordinator-fusion-contract`
- `status`: `review-handoff-ready`
- `learning_level`: `deep`
- `depends_on`: `2026-08-19-persist-risk-decision`
- `feature_branch`: `codex/define-coordinator-fusion-contract`

## 动机与范围

Coordinator 已有多个 Specialist Recommendation，但没有稳定的汇总输入/输出 Contract，无法展示多 Agent 如何形成统一候选处置。本 Change 冻结 Fusion v1.0.0：绑定同一 Run 与 Coordinator Execution，记录各 Recommendation 引用、冲突摘要、候选动作、显式排名和 provenance。Fusion 输出是后续 Risk Gate 的 subject，不读取 Risk Decision。

## 非目标

不调用模型，不修改 Recommendation/Risk 事实，不执行 Risk Gate，不创建 Approval，不调用 Java Business API，不实现最终处置、不做 HTTP/Evaluation，也不修改 `dataset/`。

## 已知后续依赖

当前 Risk Decision v1 绑定单个 Specialist Recommendation，不能表达“Fusion 后再 Risk”的顶层架构顺序。后续必须通过独立 Change 扩展 Risk subject binding；本 Change 不静默修改已冻结 Risk Contract/Persistence。

## 学习等级

`deep`。首次定义跨 Agent 汇总的 provenance、冲突和确定性排序语义；虽然复用已有 Contract canonical/idempotency 模式，但新增聚合不变量。
