# FactoryOps Workflow Run Contract

## 这个 Contract 表达什么

`Workflow Run` 表示一个 Quality Incident 的完整多 Agent 处理流程。它不是某个 Agent 的一次模型调用，也不内嵌 Agent Task、Agent Execution 或 Checkpoint 的完整内容。

首个版本为 `1.0.0`：

- Schema：`v1.0.0/schema.json`
- original 示例：`fixtures/valid/original-run.json`
- replay 示例：`fixtures/valid/replay-run.json`
- Python 入口：`validator.py`

## 字段所有权

| 区域 | 所有权与变化规则 |
|---|---|
| `identity` | 创建后不可变；保存身份、Run 类型、幂等键和 replay 血缘 |
| `provenance` | 创建后不可变；保存 Incident 和实际执行版本 |
| `lifecycle` | 只能按合法状态迁移更新；保存状态、revision 和时间 |
| `execution_refs` | 保存 Coordinator Execution 与最新 Checkpoint 的引用 |
| `progress` | 查询/展示摘要，不取代 Task 事实来源 |

## Original 与 Replay

Original Run：

- `original_run_id == run_id`
- 必须具有 `trigger_event_id`
- 禁止 replay 专属字段
- 后续持久化必须保证一个 `trigger_event_id` 只有一个 original

Replay Run：

- 创建新的 `run_id`，不得覆盖 original
- 必须具有 `original_run_id`、`replayed_from_run_id` 和 `replay_request_id`
- 两个血缘引用都不能指向自身
- 后续持久化必须保证一个 `replay_request_id` 只有一个 replay

单条 Validator 无法访问历史记录，因此不能证明引用存在、引用类型正确或多条记录之间没有环。这些规则属于后续 Run Lifecycle 持久化 Change。

## 校验入口

```python
from contracts.agent_run.validator import validate_run

validate_run(run_document)
```

校验顺序固定为：

1. 检查 Consumer 是否支持 `contract_version`。
2. 使用严格 JSON Schema 校验结构和条件字段。
3. 校验 original 身份、replay 自引用、时间顺序和进度计数。

错误通过 `AgentRunValidationError.issues` 返回稳定 `code`、JSON `path` 和说明。

## 重复关系

```python
from contracts.agent_run.validator import classify_run_relation

relation = classify_run_relation(first, second)
```

- 同 `run_id`、同 canonical 内容：`duplicate-identical`
- 同 `run_id`、不同合法内容：`duplicate-conflicting`
- 不同 `run_id`：`distinct`
- 任一输入非法：先拒绝，不给出关系分类

该分类用于同一 Run 快照在传输或写入边界的重复判断。Lifecycle 正常更新必须由后续 Repository 使用 `revision` 和合法迁移处理，不能拿两个不同 revision 的快照直接做“重复写入”处理。

## Consumer 规则

- 只接受显式列出的 Contract 版本。
- 不得忽略未知字段。
- 不得用 `run_id` 代替 `trigger_event_id` 或 `replay_request_id` 做创建幂等。
- 不得根据当前配置重写已保存 Provenance。
- 不得把 Evaluation ground truth、期望答案或离线标签加入 Run。
- 不得仅凭 `latest_checkpoint_id` 假定 Checkpoint 有效；恢复前必须加载并验证真实对象。

## 非目标

本目录不实现数据库、状态迁移、Kafka 接入、Coordinator、Agent Runtime、Checkpoint/Resume 或 Replay 执行。
