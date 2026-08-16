# 技术选型：Agent Execution Contract v1.0.0

## 对象定义

`Workflow Run` 是一次 Incident 工作流；`Agent Execution` 是其中一个角色的一次 attempt；`Task` 是 Coordinator 分派的工作要求。三者不能共用生命周期。

## 标识与幂等

- `execution_id`: `EXE-` + 32 位大写十六进制，稳定引用。
- `execution_key`: `EXK-` + SHA-256 大写十六进制。
- 摘要输入使用 UTF-8：`v1\n<run_id>\n<agent_role>\n<attempt>`。
- attempt 从 1 开始；retry 新建 attempt，不更新旧 attempt。

摘要带版本前缀和换行分隔，避免简单拼接歧义，并允许未来升级算法。数据库唯一约束属于后续 Change。

## 角色与 Task

- 角色固定为 `coordinator|quality|production|sla|risk`。
- Coordinator 可以无 `task_id`，因为它拥有 Workflow 编排入口。
- Specialist 必须有 `task_id`，避免无法追溯是谁、为何发起专业执行。
- v1 不允许动态自定义 Agent role；新增正式角色需要 Contract 演进。

## Provenance

Execution 显式冻结 `runtime_version`、`prompt_version`、`model_policy_version`、`tool_policy_version`、`context_policy_version` 和 `code_revision`。即便与 Run 相同也重复记录，因为 Run 表达计划/启动配置，Execution 表达实际调用配置。

## 输入与结果

- input 保存 `task_id`、`context_snapshot_id`、`evidence_refs`。
- success result 保存 `output_artifact_refs`、可选 `decision_id`、`evidence_refs`。
- failure 保存稳定 `code`、短消息、`recoverability` 和可选 `failed_dependency_ref`。
- 不保存 raw prompt、raw response、图片、mask、stack trace 或 ground truth。

## Lifecycle 与 revision

v1 快照形状支持 PENDING、RUNNING、SUCCEEDED、FAILED、CANCELLED。`revision` 供后续乐观锁使用；relation classifier 仅接受 revision + 1 且 immutable 内容不变的下一快照。它不替代状态迁移规则或事务。

## JSON Schema 与 Python Validator

采用 JSON Schema Draft 2020-12 处理结构、枚举、严格字段和状态条件；Python Validator 处理 SHA-256 key、角色/Task、时间顺序、引用唯一性和跨快照关系。这样既保持跨语言 Contract，又避免在 Schema 中写不可维护的摘要和关系逻辑。
