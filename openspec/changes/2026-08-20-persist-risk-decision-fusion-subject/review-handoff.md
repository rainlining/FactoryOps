# Review Handoff

- Change：`2026-08-20-persist-risk-decision-fusion-subject`
- 学习等级：`delegated`
- 分支：`codex/persist-risk-decision-fusion-subject`
- Worktree：`C:\Users\小霖\Desktop\work\project2\FactoryOps\.worktrees\persist-risk-decision-fusion-subject`
- stacked base：`5fe9f6d80b99546a978c5fb4d6850800a4cbbb33`
- HEAD：待最终提交

新增 migration 013，将 `risk_decisions` 扩展为 Recommendation/Fusion 互斥 subject；`RiskDecisionService.save` 按 subject 锁定来源并复用 Fusion persistence 的完整性解码，原子写入 typed columns。读取重新验证 Decision 与完整 Fusion provenance；历史 replay 不要求 Coordinator Execution 仍 RUNNING。

不运行 Risk Agent，不推进状态，不执行 Approval/Java Business Action，不修改 `dataset/`。

验证：Risk MySQL 12 passed、migration 回归 39 passed、Agent 171 passed、Contract 135 passed、Java verify 退出码 0、Ruff/diff/dataset checks 通过。独立审查结果将在最终 HEAD 记录。

建议阅读：proposal/spec/design → migration 013 → `RiskDecisionService.save`/`_decode`/`_decode_fusion` → `test_risk_decision_mysql.py`。Review 期间禁止并行修改该 worktree。
