# Change 提案：2026-08-16-define-agent-execution-contract

## 元数据

- `change_id`: `2026-08-16-define-agent-execution-contract`
- `status`: `completed`
- `learning_level`: `deep`
- `first_deep_reference`: `N/A`
- `depends_on`: `[2026-08-15-define-agent-run-contract, 2026-08-15-persist-agent-run-lifecycle, 2026-08-15-start-agent-run-from-inbox]`
- `spec_refs`: `[agent-run-contract, agent-run-lifecycle-persistence, agent-run-inbox-start]`
- `implementation_session`: `current planning-and-implementation session`
- `review_session`: `pending`

## 为什么要做

可信 Incident 现在能够形成唯一 `PENDING` Workflow Run，但系统还不能表示 Coordinator 或专业 Agent 的一次具体执行。若直接实现 Coordinator，attempt、输入引用、输出引用、失败分类和版本事实会散落在运行时代码中，无法稳定支持审计、并行、恢复、Replay 和 Evaluation。

## 范围

- 本 Change 唯一核心能力：冻结 Agent Execution v1.0.0 的严格版本化 Contract。
- 定义 Coordinator、Quality、Production、SLA、Risk 五种 Agent 角色。
- 定义 Execution 身份、所属 Workflow Run、attempt 与幂等键。
- 定义输入引用、冻结的执行 Provenance、生命周期、结构化结果和失败分类。
- 提供 JSON Schema、合法/非法 fixture、Validator、canonical form 和关系分类器。
- 提供 README、技术选型文档和 Contract Test。

## 非目标

- Agent Execution、Task 或 Checkpoint 的数据库表、migration 和 Repository。
- `PENDING` Run claim、Run Lease、Redis Lock 或 `RUNNING` 迁移。
- Coordinator Worker、Task Dispatch、Parallel Execution 或 Agent 业务推理。
- LLM、Prompt 内容、Model Adapter、Tool Call、Java Business API 或审批执行。
- Checkpoint、Resume、Replay 执行、通用 Trace/Metrics 平台或 Evaluation Harness。
- 修改 `dataset/`。

## 预期影响

- 新增规格：`agent-execution-contract`。
- 代码区域：`contracts/agent_execution/`。
- 外部 Contract：新增 v1.0.0；不修改现有 Contract。

## 依赖与顺序

- Run Contract 提供 Workflow 级身份和 Provenance 边界。
- Run Lifecycle Persistence 提供合法父 Run 的事实来源。
- Inbox Start 保证 original Run 先于 Execution 存在。
- 后续依次可实现 Execution 持久化、Run claim/Coordinator 启动和 Task Contract。

## 学习等级理由

`deep`。Schema、fixture 和 Validator 的工程模式复用首次 deep 的 Run Contract Change，但本 Change 首次引入单 Agent attempt、Execution 幂等身份、可变 revision、失败可恢复性和输出所有权。这些是新的并发及失败语义，不能按重复模式降级。

## 验收摘要

- 技术验收：合法 fixture 通过；未知字段、ground truth、非法角色、attempt/key 不一致、非法生命周期、失败/结果互斥及非法 revision 关系被稳定拒绝或分类；所有 Contract 回归通过。
- 学习验收：在独立 Review/Learning 会话完成 Walkthrough、Owner 修改、failure/debug exercise 和最终 diff 接受。
