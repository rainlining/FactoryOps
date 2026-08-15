# 技术设计：Workflow Run Contract v1.0.0

## 1. 结论与边界

本 Change 定义 `Workflow Run`：一个 Quality Incident 的完整多 Agent 处理流程。单个 Coordinator 或 Specialist 的一次调用称为 `Agent Execution`，不在本 Contract 中定义。

```text
Quality Incident
└── Workflow Run
    ├── Coordinator Agent Execution
    ├── Specialist Agent Executions
    ├── Agent Tasks
    └── Checkpoints
```

Contract 是严格的当前快照，不是数据库模型，也不保存完整状态历史。

## 2. 三类数据所有权

```text
identity   ── 创建后不可变：Run 身份、类型、幂等键和 replay 血缘
provenance ── 创建后不可变：输入归属和实际执行版本
lifecycle  ── 按合法迁移更新：状态、revision 和时间
```

`execution_refs` 保存关键对象引用；`progress` 仅是查询和展示摘要。完整 Agent Execution、Task、Checkpoint 由后续独立 Contract 持有，并通过 `workflow_run_id` 反向归属。

## 3. 身份与幂等

- `run_id` 是不编码业务语义的稳定引用。
- original 以 `trigger_event_id` 幂等；Kafka redelivery、Consumer 重启或重复启动不能产生第二个 original。
- replay 以 `replay_request_id` 幂等；同一重放请求重复提交不能产生多个 replay。
- 相同 Incident 可以拥有一个 original 和任意多个合法 replay，因此不能以 `incident_id` 作为 Run 幂等键。

本 Contract 只能验证单条记录的字段组合。跨记录唯一性必须由后续数据库唯一键和事务证明。

## 4. Replay 血缘

Replay 同时保存：

- `original_run_id`：整个血缘的根 original；
- `replayed_from_run_id`：本次 replay 的直接来源。

```text
A original: original=A, replayed_from=空
B replay:   original=A, replayed_from=A
C replay:   original=A, replayed_from=B
```

双引用使 Evaluation 能快速聚合同一 original 的所有实验，同时保留每次 replay 复制配置或 Checkpoint 的直接来源。单条 Validator 能拒绝自引用，但引用存在性、引用类型和跨记录循环必须在持久化 Change 中验证。

## 5. Provenance

每个 Run 必须冻结：

- `incident_id`
- `runtime_version`
- `workflow_version`
- `prompt_set_version`
- `model_policy_version`
- `tool_policy_version`
- `context_policy_version`
- `code_revision`
- `created_at`

字段保存版本或引用，而不复制完整 Prompt、Context、模型响应或 Tool 结果。Replay 不被迫沿用原配置；它必须记录自己实际使用的版本，从而支持同配置可重复性实验和跨版本对比实验。

## 6. Lifecycle

| 状态 | 含义 | 分类 |
|---|---|---|
| `PENDING` | 已接受但尚未开始 | 非终态 |
| `RUNNING` | Coordinator 正在推进 | 非终态 |
| `WAITING_FOR_APPROVAL` | 正常等待人工审批 | 非终态 |
| `SUSPENDED` | 技术性或操作性暂停，允许恢复 | 非终态 |
| `SUCCEEDED` | 成功完成 | 终态 |
| `FAILED` | 已确认无法继续 | 终态 |
| `CANCELLED` | 被明确取消 | 终态 |

`revision` 为非负整数，后续用作乐观锁版本。首次进入 `RUNNING` 后 `started_at` 固定；终态必须具有 `ended_at`。`status_reason` 只保存稳定原因码和简短说明，不保存完整异常堆栈。

本 Change 不冻结完整状态迁移图。`persist-agent-run-lifecycle` 将定义允许边、事务、并发冲突和终态保护。

## 7. 严格版本演进

- 版本格式使用 SemVer，首版为 `1.0.0`。
- 所有对象拒绝未知字段，不提供自由格式 `metadata` 或 `extensions`。
- 新增不改变既有含义的可选字段升级 minor。
- 删除、改名、约束收紧或状态语义变化升级 major。
- Consumer 必须显式声明支持版本。

严格策略让旧 Consumer 尽早失败，而不是对新字段作出不可解释的忽略。

## 8. 校验顺序与关系分类

Validator 按以下顺序执行：

1. 检查 `contract_version` 是否受支持，避免加载任意路径。
2. 使用 JSON Schema 校验结构、类型、枚举、严格字段和条件字段。
3. 校验 Schema 无法表达或不宜表达的跨字段不变量。
4. 只有两份输入均合法时才进行关系分类。

关系分类使用 canonical JSON：

- 相同 `run_id` 且内容相同：`duplicate-identical`；
- 相同 `run_id` 但内容不同：`duplicate-conflicting`；
- 不同 `run_id`：`distinct`；
- 任一输入非法：拒绝，不分类。

这不是跨 Run 的 replay 血缘分类；它用于识别同一 Run 快照传输或持久化时的重复与冲突。

## 9. 失败路径

- 不支持版本：加载 Schema 前拒绝。
- 未知字段或 ground truth：Schema 拒绝并给出字段路径。
- original/replay 字段组合错误：Schema 或语义 Validator 拒绝。
- 自引用 replay：语义 Validator 拒绝。
- 终态时间倒序：语义 Validator 拒绝。
- 完成任务数超过总数：语义 Validator 拒绝。
- 同 `run_id` 出现不同合法内容：分类为 `duplicate-conflicting`，交由调用方隔离，不自动覆盖。

## 10. 测试策略

- Schema 测试确认 v1.0.0 文件存在并接受 original/replay fixtures。
- Validator 测试覆盖版本、严格字段、身份组合、血缘自引用、状态时间和进度不变量。
- Fixture 测试为每个关键失败边界固定错误码和 JSON path。
- Relation 测试覆盖 canonical key 顺序、identical、conflicting、distinct 和非法输入前置拒绝。
- 回归运行仓库全部 Python Contract 测试，确认 Vision 与业务事件 Contract 不受影响。

## 11. 安全与 Context 边界

Run 不包含图片、大型 Artifact、凭据、完整 Prompt、完整 Context、模型响应或 Evaluation ground truth。Ground truth 只能存在于隔离的 Evaluation Harness，不能进入 Agent 可读取的 Contract。

## 12. 被放弃的方案

- 将整个流程和单 Agent 调用都称为 AgentRun：会混淆整体 replay 与单次模型 retry。
- 允许多个 unrelated original：无法区分 redelivery 与重新执行。
- 仅保存一个 replay 来源：无法同时高效聚合根实验和还原直接来源。
- 使用 Incident ID 幂等：会阻止合法 replay。
- 在 Run 中内嵌所有 Task/Checkpoint：对象持续膨胀并产生版本循环依赖。
- 宽松未知字段或自由 metadata：不同 Consumer 会形成不同语义。
- 将 `RETRYING`、`RESUMING` 设为状态：短暂动作会造成持久状态膨胀。
- 进程崩溃立即标记 `FAILED`：会破坏 Checkpoint/Resume 的恢复语义。
