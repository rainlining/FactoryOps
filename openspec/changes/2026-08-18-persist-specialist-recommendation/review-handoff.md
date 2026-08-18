# Review Handoff

- Change：`2026-08-18-persist-specialist-recommendation`，`standard`
- 分支：`codex/persist-specialist-recommendation`
- worktree：`C:\Users\小霖\Desktop\work\project2\FactoryOps\.worktrees\persist-specialist-recommendation`
- stacked base：`36bd13f0532ce6d6860b513fe9de90a20fb65678`
- upstream：`codex/define-specialist-recommendation-contract`
- 状态：`review-handoff-ready`

## 范围与调用链

migration 010 创建 immutable Recommendation 表。入口 `SpecialistRecommendationService.save`：Contract canonicalize → recommendation-key advisory lock → key/ID 查重 → Task 行锁 → Execution 行锁 → current RUNNING pair 校验 → typed columns + canonical LONGTEXT + SHA-256 INSERT → commit → finally 释放 lock。已存在事实先分类，因此 Completion 后仍可 identical replay。

读取入口 `get_by_key`：hash → JSON parse → Contract validate → identity/action/severity/generated_at typed columns 双向核对；损坏数据抛 `RecommendationPersistenceIntegrityError`。保存不修改 Task、Execution 或 lease，不存模型原文，不包含 Model/Tool、Risk/Fusion、Completion、Java API、Evaluation 或 `dataset/`。

## Review 路线

按 proposal/design → migration 010 → result/error types → `save` admission/锁序 → `_validate_parent` → `_decode` 完整性 → fixtures adapter tests 阅读。重点复现并发 conflicting、Completion 后 replay、同 ID 跨 Execution 和 hash/typed column 篡改。

验证：局部 `8 passed`，相关组合 `46 passed`，Contract `116 passed`，Java `65 tests`，最终 Agent 数字见 verification；Ruff/diff/dataset 检查通过。Standard Review 建议实际运行 typed-column corruption 测试并解释为何已有事实 replay 不再要求 parent RUNNING。Review 期间禁止并发修改本 worktree，验收前不得归档或合并 main。
