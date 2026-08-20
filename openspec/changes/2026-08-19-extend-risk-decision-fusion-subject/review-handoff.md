# Review Handoff

- Change：`2026-08-19-extend-risk-decision-fusion-subject`
- 学习等级：`delegated`
- 分支：`codex/extend-risk-decision-fusion-subject`
- Worktree：`C:\Users\小霖\Desktop\work\project2\FactoryOps\.worktrees\extend-risk-decision-fusion-subject`
- stacked base：`d5dba59c52a0121f1df7f227c6817683fecab89d`
- HEAD：待提交

入口为 `validate_risk_decision(payload, recommendation_identity=... | fusion_identity=...)`。v1.0 保持 Recommendation binding；v1.1 通过 `subject_type=FUSION` 绑定 Fusion id/key/run/coordinator execution/round，并由 Fusion key 派生 decision key。未实现持久化、Risk Agent、Approval 或业务动作。

首审发现并修复 2 个 Important：v1.1 canonical/relation 版本支持和 subject 字段互斥；同时收紧 source 参数混用并修正 subject key 错误文案。复审为 0 Critical、0 Important。Contract 局部 10 passed、全 Contract 135 passed、Ruff/Schema 通过。Agent/Java 的 Testcontainers 全量因 Docker named pipe 不可用未通过，详见 verification.md；不得把环境失败伪装成代码通过。
