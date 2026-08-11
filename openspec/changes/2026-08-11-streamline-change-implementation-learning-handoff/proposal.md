# Change 提案：2026-08-11-streamline-change-implementation-learning-handoff

## 元数据

- `change_id`: `2026-08-11-streamline-change-implementation-learning-handoff`
- `status`: `technically-verified`
- `learning_level`: `standard`
- `first_deep_reference`: `N/A`
- `depends_on`: `[2026-08-10-establish-openspec-learning-governance]`
- `spec_refs`: `[development-governance]`
- `implementation_session`: `current Codex task`
- `review_session`: `pending`

## 为什么要做

首个 Deep Change 证明逐 Stage owner review 会把规划、编码和学习频繁交错，显著降低工程推进速度。项目所有者决定把实现与学习拆成两个独立会话：实现会话连续交付技术结果，Review/Learning 会话集中完成理解、修改、调试和最终接受。

## 范围

- 本 Change 唯一核心能力：建立连续实现与跨会话 Review Handoff 治理。
- 修改中文 `AGENTS.md`、OpenSpec 工作流、已生效治理规格和 Change 模板。
- 新增统一的 `review-handoff.md` 模板。

## 非目标

- 不修改 FactoryOps 业务代码、Contract、数据库、Kafka 或 Agent Runtime。
- 不取消 Change 范围控制、TDD、内部小提交或技术验证。
- 不取消 Deep Learning Gate，也不允许未通过门禁的 Deep Change 合并 `main`。
- 不允许两个会话并发修改同一 worktree。

## 预期影响

- 修改规格：`development-governance`。
- 文档区域：`AGENTS.md`、`openspec/`。
- 外部 Contract：无。

## 学习等级理由

本 Change 为 `standard`。它改变开发治理和交接流程，但不引入业务算法、事务、并发或运行时失败语义。项目所有者需要 review 生命周期和会话责任边界，不需要 Deep 故障实验。

## 验收摘要

- 技术验收：治理文件、模板、状态和范围的一致性检查。
- 学习验收：独立 Review 会话确认新生命周期与不可绕过的 Learning Gate。
