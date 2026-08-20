# Review Handoff

- Change：`2026-08-20-persist-risk-decision-fusion-subject`
- 学习等级：`delegated`
- 分支：`codex/persist-risk-decision-fusion-subject`
- Worktree：`C:\Users\小霖\Desktop\work\project2\FactoryOps\.worktrees\persist-risk-decision-fusion-subject`
- stacked base：`5fe9f6d80b99546a978c5fb4d6850800a4cbbb33`
- 实现与复审 HEAD：`3dcc3f0c386573742876078ad60879889df9fd66`
- 最终 handoff metadata commit：本文件所在的 branch HEAD

新增 migration 013，将 `risk_decisions` 扩展为 Recommendation/Fusion 互斥 subject；`RiskDecisionService.save` 按 subject 锁定来源并复用 Fusion persistence 的完整性解码，原子写入 typed columns。读取重新验证 Decision 与完整 Fusion provenance；历史 replay 不要求 Coordinator Execution 仍 RUNNING。

不运行 Risk Agent，不推进状态，不执行 Approval/Java Business Action，不修改 `dataset/`。

验证：Risk MySQL 13 passed、migration 回归 46 passed、Agent 172 passed、Contract 135 passed、Java verify 退出码 0（20 reports/65 tests/0 failures/errors/skipped）、Ruff/diff/dataset checks 通过。

独立审查首轮发现并修复 1 个 Important：migration 013 的阶段性 DDL 已提交但 history 未写时不可重试。runner 现在按数据库事实恢复完整列/约束阶段，并拒绝无法安全推断的部分 schema；真实 MySQL 覆盖两个 DDL 阶段的恢复。同一子 Agent 复审为 0 Critical、0 Important（局部 13 passed）。

建议阅读：proposal/spec/design → migration 013 → `RiskDecisionService.save`/`_decode`/`_decode_fusion` → `test_risk_decision_mysql.py`。Review 期间禁止并行修改该 worktree。
