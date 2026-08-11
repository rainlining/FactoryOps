# Change 学习计划：2026-08-11-streamline-change-implementation-learning-handoff

## 学习元数据

- `learning_level`: `standard`
- `pattern_stage`: `N/A`
- `first_deep_reference`: `N/A`
- `gate_status`: `not-started`

## Review 目标

- 能区分实现会话的 `technically-verified` 与 Review 会话的 `completed`。
- 能说明为什么取消逐 Stage 停顿不等于允许巨大 diff。
- 能说明 Deep Change 为什么必须在 feature branch 等待 Learning Gate。
- 能说明 handoff 的 branch/worktree/base/head 如何防止审错代码或并发写入。

## Code Walkthrough 路线

1. `AGENTS.md` 的生命周期、连续 Apply 和双会话职责。
2. `openspec/README.md` 的操作流程。
3. `openspec/config.yaml` 的生成规则。
4. `openspec/specs/development-governance/spec.md` 的可验证场景。
5. `_templates/review-handoff.md` 的恢复与门禁字段。

## Standard Review Gate

- [ ] 能解释新生命周期。
- [ ] 能解释两个会话的单写入者约束。
- [ ] 能确认 Learning Gate 和 main 合并门禁仍然存在。
- [ ] 已 review 最终 diff 并明确接受。

本 Change 不涉及运行时代码，owner code modification 和 failure/debug exercise 为 `N/A`。
