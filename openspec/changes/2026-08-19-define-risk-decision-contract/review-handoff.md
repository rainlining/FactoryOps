# Review Handoff

- Change：`2026-08-19-define-risk-decision-contract`
- 学习等级：`deep`；状态：`review-handoff-ready` / `awaiting-learning-gate`
- 分支：`codex/define-risk-decision-contract`
- Worktree：`C:\Users\小霖\Desktop\work\project2\FactoryOps\.worktrees\define-risk-decision-contract`
- Stacked base：`67fc8160c78946ea4bcb53cdf9b17de2f2f9f5ee`
- 实现提交：`5514dc7`（`feat(contract): define risk decisions`）。
- 最终 HEAD：包含本 handoff 回填的随后文档提交；Review 恢复时以 `git rev-parse origin/codex/define-risk-decision-contract` 为唯一远端事实。

## 实现范围

冻结 Risk Decision v1.0.0 Schema、Recommendation identity binding、decision/risk/approval Gate、canonical JSON、decision key 和 identical/conflicting/distinct 分类。`STOP_LINE` 强制 HIGH + REQUIRE_APPROVAL；`allowed_actions` 与 decision 一致。Risk 只做 Gate，不执行动作、不写库、不调用 Java/Approval API。

## 真实调用链与文件

Contract 使用者入口为 `contracts.risk_decision.validator.validate_risk_decision(payload, recommendation_identity)`；它先校验 payload，再逐字段验证源 Recommendation binding。随后可调用 `canonicalize_risk_decision` 和 `classify_risk_decision_relation`。Schema 在 `contracts/risk_decision/v1.0.0/schema.json`，回归在 `contracts/risk_decision/tests/test_validator.py`。失败路径包括 identity mismatch、未知字段、非法 key、重复数组、非有限 confidence、ground truth 注入、STOP_LINE 审批不一致和 allowed action 不一致。

## 验证

详见 `verification.md`：审查修复后局部 8 passed、全 Contract 124 passed、Agent 152 passed；Java 65 tests 全通过，Ruff/Schema/diff/dataset 检查通过。

独立子 Agent 复审 `d924339`：此前两个 Important 均关闭，未发现新的 Critical/Important。非阻塞 Minor：identity mismatch 参数化测试未单列 recommendation_key，但生产循环已覆盖该字段。

## Learning Gate

Owner 修改任务：新增一个 `HOLD_BATCH` 的合法 ALLOW fixture，并说明为什么 proposed action 必须出现在 allowed_actions。Failure/debug exercise：将 STOP_LINE 改为 ALLOW 且 `approval_required=false`，观察 `high_risk_approval_required`；再将 REQUIRE_APPROVAL 的 allowed_actions 加回 STOP_LINE，观察 `allowed_action_mismatch`。清理：恢复 fixture 并重新运行 Contract tests。当前未由 Owner 完成，禁止标记 completed/archive。

## 恢复与阅读顺序

在独立 Review/Learning 会话中确认 worktree 干净后，依次阅读 `proposal.md`、`specs/risk-decision-contract/spec.md`、`design.md`、`contracts/risk_decision/validator.py`、测试和本 handoff。不得与实现会话并发修改此 Change；恢复命令：`git fetch origin; git switch codex/define-risk-decision-contract; git status --short`。
