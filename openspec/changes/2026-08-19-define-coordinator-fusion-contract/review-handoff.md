# Review Handoff

## 基本信息

- Change：`2026-08-19-define-coordinator-fusion-contract`
- 学习等级：`deep`（用户 Review/Learning Gate 延后至 demo milestone）
- 分支：`codex/define-coordinator-fusion-contract`
- Worktree：`C:\Users\小霖\Desktop\work\project2\FactoryOps\.worktrees\define-coordinator-fusion-contract`
- stacked base：`e8094d77716b175e2a5040daa2bd85711edaf5a4`
- 当前实现提交：待提交

## 实现范围

新增 `contracts/coordinator_fusion/`，冻结 Coordinator Fusion Contract v1.0.0、JSON Schema、valid fixture、Python validator、canonical bytes 和 relation classification。入口为 `validate_coordinator_fusion(payload, source_recommendations)`；核心调用链为 schema/preflight → source Recommendation 校验与 identity 比对 → run/role/candidate/conflict 不变量 → canonicalization/classification。

Fusion 绑定 `run_id`、`coordinator_execution_id`、`round`，输出候选动作和 provenance，`authorization_state` 固定为 `NOT_EVALUATED`。不执行 Risk、Approval 或 Business Action，也不修改 `dataset/`。

## 验证

Contract 130 passed，Fusion 局部 6 passed，Agent Service 161 passed，Java `mvn verify -q` 65 tests/0 failures/0 errors/0 skipped，Ruff、JSON Schema、`git diff --check` 均通过；dataset 状态无修改。完整证据见 `verification.md`。

## Review 路线

建议阅读顺序：`proposal.md` → `specs/coordinator-fusion-contract/spec.md` → `design.md`/`technical-decisions.md` → `contracts/coordinator_fusion/v1.0.0/schema.json` → `validator.py` → `tests/test_validator.py`。

Review 重点：输入 Recommendation 引用是否完整且不可篡改、角色覆盖与候选 rank 不变量、canonical relation 语义，以及 Fusion 不越过 Risk/Approval 边界。后续 Risk subject binding 扩展必须另立 Change。

恢复命令：在该 worktree `git switch codex/define-coordinator-fusion-contract`，确认 base 与 handoff 一致后运行上述验证。Review/Learning 期间不要与实现会话并行修改该 Change/worktree。
