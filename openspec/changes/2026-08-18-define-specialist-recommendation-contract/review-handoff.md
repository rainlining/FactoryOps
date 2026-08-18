# Review Handoff

- Change：`2026-08-18-define-specialist-recommendation-contract`，`deep`
- 分支：`codex/define-specialist-recommendation-contract`
- worktree：`C:\Users\小霖\Desktop\work\project2\FactoryOps\.worktrees\define-specialist-recommendation-contract`
- stacked base：`2628b5cc306645e898cbed7e3a18159774bf5fd6`
- upstream：`codex/retry-worker-task-execution`
- implementation commit：`8960d19`
- 状态：`review-handoff-ready`

## 范围与调用链

新增 `contracts/specialist_recommendation` v1.0.0：三份合法 fixture、ground-truth/角色 mismatch 非法 fixture、严格 Draft 2020-12 Schema、Validator、canonical form 和 relation classifier。入口 `validate_recommendation`：版本 → finite preflight → role/details preflight → Schema → deterministic key → 数组唯一性。`compute_recommendation_key` 绑定 Execution attempt；`classify_recommendation_relation` 返回 identical/conflicting/distinct。

不包含 Risk Gate、最终 Decision、Model/Tool、Prompt/Context、持久化、Worker Completion、Fusion、Java API 或 Evaluation。金额仅是 Agent 建议估算，不产生业务副作用；模型原文和长解释只能用 Artifact 引用。

## Review 路线

按 proposal/design → Schema 公共 envelope → 三个 role details → valid/invalid fixtures → `compute_recommendation_key` → `validate_recommendation` preflight/Schema/key/unique → canonical/relation → tests 阅读。重点复现 NaN、role mismatch、ground truth 和同 key conflicting。

验证：实现移交时局部 `16 passed`、全 Contract `115 passed`、Agent `144 passed`、Java `65 tests`；Review 收尾后局部 `17 passed`、全 Contract `116 passed`，Schema/Ruff/diff/dataset 检查通过。Owner 修改由 Codex 代做：Production affected order refs 的 64 项唯一上界被接受，重复项精确拒绝。Failure exercise 使用合法 SLA payload 注入 `expected_action`，实际得到 `schema_validation_failed` at `$.expected_action`。由于 Owner 修改不是项目所有者亲自完成，Deep Learning Gate 不自动通过。Review 期间禁止并发修改本 worktree。
