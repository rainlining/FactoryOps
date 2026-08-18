# Change 提案：持久化 Specialist Recommendation

- `change_id`: `2026-08-18-persist-specialist-recommendation`
- `status`: `review-handoff-ready`
- `learning_level`: `standard`
- `depends_on`: `2026-08-18-define-specialist-recommendation-contract`
- `feature_branch`: `codex/persist-specialist-recommendation`

## 动机与范围

Recommendation Contract 已冻结，但输出仍无法成为可重放、可融合的数据库事实。本 Change 新增 migration 010 和持久化 Service：只接受严格 Contract，校验它绑定 current RUNNING Specialist Execution/Task，并原子保存 canonical payload、hash 和查询列；相同 key 返回 identical/conflicting。

## 非目标

不调用 Model/Tool，不完成 Execution/Task，不保存模型原文，不实现 Risk/Fusion、Artifact Store、HTTP/Java API、自动 retry、Evaluation，也不修改 `dataset/`。

## 学习等级

`standard`。复用 `2026-08-18-start-worker-task-execution` 首次 deep 的固定行锁、父对象一致性、单事务回滚和幂等事实模式；新增点是 immutable Recommendation canonical JSON，没有新的 ownership 或状态机。
