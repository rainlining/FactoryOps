# Change 提案：持久化 Risk Decision Fusion Subject

- `change_id`: `2026-08-20-persist-risk-decision-fusion-subject`
- `status`: `review-handoff-ready`
- `learning_level`: `delegated`
- `depends_on`: `2026-08-19-extend-risk-decision-fusion-subject`
- `feature_branch`: `codex/persist-risk-decision-fusion-subject`

Risk Decision v1.1 已允许绑定 Fusion，但现有 persistence 只保存 Recommendation FK。本 Change 扩展 Risk Decision persistence，使 Recommendation/Fusion 两种 subject 都能原子保存、稳定 replay，并在读取时校验对应来源事实。

非目标：不运行 Risk Agent，不实现 Approval/Business Action/HTTP，不修改已冻结 Contract，不修改 `dataset/`。

学习等级为 `delegated`，复用 Risk Persistence 的 advisory lock、immutable fact、canonical hash 和完整性读取模式；新增仅为 subject-specific parent binding。
