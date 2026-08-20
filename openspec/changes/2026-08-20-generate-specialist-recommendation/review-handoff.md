# Review Handoff

- Change：`2026-08-20-generate-specialist-recommendation`
- 学习等级：`deep`（Owner Review/Learning 延后）
- 分支：`codex/generate-specialist-recommendation`
- Worktree：`C:\Users\小霖\Desktop\work\project2\FactoryOps\.worktrees\generate-specialist-recommendation`
- stacked base：`ccf2bd748b26e92af870e57075b68381c068638d`
- HEAD：待首次实现提交

新增 provider/context/draft 边界、显式配置的 `RecordedSpecialistProvider` 和 `SpecialistRecommendationGenerationService.generate`。调用链：deterministic key → existing replay short-circuit → Task/Execution typed preflight → provider（无数据库事务）→ 应用层构造 identity/Contract → Recommendation persistence 事务重新 fencing parent。

非目标：不调用真实模型，不读取 dataset/ground truth，不完成 Execution/Task，不生成 Fusion/Risk，不实现 HTTP/Kafka/Approval/Java Action。

真实验证：局部 8 passed、相关 MySQL 29 passed、Agent 190 passed、Contract 135 passed、Java 65 tests/0 failures、Ruff/diff/dataset checks 通过。

已知上游事项：通用 Execution reader 会拒绝 Worker start 写出的空 status reason message；本 Change 使用最小 typed preflight，详见 verification。Review 应判断这是否可以作为独立 follow-up，还是构成本 Change 的安全阻塞。

建议阅读：proposal/spec/design → `specialist_generation.py` 的 context/draft/provider → `generate`/`_read_pair`/`_validate_pair` → `SpecialistRecommendationService.save` → `test_specialist_generation_mysql.py`。重点审查 ground-truth 隔离、provider 信任边界、replay shortcut、外部调用期间无事务和保存 fencing。Review 期间禁止并行修改本 worktree。
