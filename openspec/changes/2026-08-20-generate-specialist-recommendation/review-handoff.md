# Review Handoff

- Change：`2026-08-20-generate-specialist-recommendation`
- 学习等级：`deep`（Owner Review/Learning 延后）
- 分支：`codex/generate-specialist-recommendation`
- Worktree：`C:\Users\小霖\Desktop\work\project2\FactoryOps\.worktrees\generate-specialist-recommendation`
- stacked base：`ccf2bd748b26e92af870e57075b68381c068638d`
- reviewed implementation HEAD：`b160acc40f8c756678b8c5db997691cd3aba0192`
- handoff HEAD：本文件所在最终文档提交（推送后以远端分支 HEAD 为准）

新增 provider/context/draft 边界、显式配置的 `RecordedSpecialistProvider` 和 `SpecialistRecommendationGenerationService.generate`。调用链：Execution 完整 Contract reader → provider provenance 校验 → existing terminal-safe replay shortcut → 首次生成的 Task 完整 Contract/current pair preflight → provider（无数据库事务）→ evidence/artifact authorization → 应用层构造 identity/Contract → Recommendation persistence 事务重新 fencing parent/context snapshot/六项 provenance。

非目标：不调用真实模型，不读取 dataset/ground truth，不完成 Execution/Task，不生成 Fusion/Risk，不实现 HTTP/Kafka/Approval/Java Action。

真实验证：generation 11 passed、相关 MySQL 合计 40 passed、Agent 193 passed、Contract 135 passed、Java 65 tests/0 failures；修改文件 Ruff/format、diff/dataset checks 通过。全 Agent Ruff 的 22 个既有 import-order baseline finding 未混入本 Change。

独立审查首轮 5 个 Important、复审 2 个 Important 已全部修复；最终复审为 0 Critical、0 Important。Worker Start/Retry/Completion 的既有 reason message 完整性也已修复，生成入口不再绕过 lifecycle Contract reader。

建议阅读：proposal/spec/design → `specialist_generation.py` 的 provenance/context/draft/provider → `generate`/`_validate_pair` → `SpecialistRecommendationService.save(expected_execution_provenance=...)` → Worker reason message 写入 → `test_specialist_generation_mysql.py`。重点审查 ground-truth/evidence 隔离、provider 信任边界、terminal replay、外部调用期间无事务和保存 fencing。Review 期间禁止并行修改本 worktree。
