# Review Handoff

- Change：`2026-08-20-evaluate-fusion-risk-decision`
- 学习等级：`deep`（Owner Learning Gate 延后）
- 分支：`codex/evaluate-fusion-risk-decision`
- Worktree：`C:\Users\小霖\Desktop\work\project2\FactoryOps\.worktrees\evaluate-fusion-risk-decision`
- stacked base：`fb6815691a30af863879ad4a91e20865c8cfa6df`
- HEAD：待首次实现提交

实现 `FusionRiskEvaluationService.evaluate`：完整读取 Fusion → `evaluate_fusion_policy` 确定性矩阵 → 构造绑定完整 Fusion identity 的 v1.1 Risk Decision → 既有 persistence 重新锁定/校验并保存。Decision key/ID 确定派生，调用方提供稳定 generated_at；相同 command 可并发 replay。

非目标：不调用 LLM、不实现 Approval、不推进生命周期、不调用 Java Business API、不执行业务动作、不修改 Contract/schema/`dataset/`。

真实验证：局部 10 passed、相关 MySQL 30 passed、Agent 182 passed、Contract 135 passed、Java 65 tests/0 failures、Ruff/diff/dataset checks 通过。

独立审查首轮 2 个 Important 已修复：ESCALATE 现为进入人工流程的 LOW/ALLOW 路由；Risk save 在同一事务锁定并重验完整 Fusion provenance，真实并发证明来源破坏不能先于 Decision 提交。最终复审结果待记录。

建议阅读：proposal/spec/design → `fusion_risk_evaluation.py::evaluate_fusion_policy` → `FusionRiskEvaluationService.evaluate` → Risk persistence `save` → `test_fusion_risk_evaluation_mysql.py`。重点审查 policy matrix、审批前授权语义、deterministic identity、TOCTOU 再校验和并发 replay。Review 期间禁止并行修改本 worktree。
