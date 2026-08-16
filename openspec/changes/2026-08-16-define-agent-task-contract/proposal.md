# Change 提案：2026-08-16-define-agent-task-contract

## 元数据

- `change_id`: `2026-08-16-define-agent-task-contract`
- `status`: `design-reviewed`
- `learning_level`: `deep`
- `first_deep_reference`: `N/A`
- `depends_on`: `[2026-08-16-define-agent-execution-contract]`
- `base_branch`: `codex/define-agent-execution-contract`
- `feature_branch`: `codex/define-agent-task-contract`

## 为什么要做

Workflow Run 和单次 Agent Execution 已有结构化边界，但 Coordinator 仍无法持久表达“分派给哪个专业角色、基于什么输入、依赖哪些前置工作、是否已经完成”的工作单元。缺少 Task Contract 时，dispatch、retry、依赖和恢复会退化为进程内临时状态。

## 范围

- 定义 Agent Task v1.0.0 严格 Contract。
- 固定四种专业 Task type 与目标 Agent role 映射。
- 定义 Run 内稳定 request 幂等、输入/依赖引用、生命周期、成功/失败事实。
- 提供 Schema、fixtures、Validator、canonical form、关系分类和 Contract Test。
- 提供中文设计、技术选型、学习与 handoff 工件。

## 非目标

- Task 数据库、migration、Repository、dispatch Worker 或并行调度。
- Coordinator、专业 Agent、LLM、Tool、Context Assembly 的真实执行。
- Execution 创建/持久化、retry policy、Run claim/lease、Checkpoint/Resume。
- Java API、审批、业务副作用、Evaluation 和 `dataset/`。

## 学习等级理由

`deep`。Contract 实现模式可复用，但 Task 首次定义 dispatch 幂等、依赖图、Task/Execution 所有权以及终态聚合失败模型，属于新的并发和恢复语义。

## 验收摘要

- 技术：合法四角色 Task 通过；未知字段、ground truth、role/type 不匹配、key 错误、自依赖、终态形状、时间和 revision 冲突被稳定处理；全仓回归通过。
- 学习：独立 Review/Learning 会话完成 Walkthrough、Owner 修改、故障实验和 diff 接受。
