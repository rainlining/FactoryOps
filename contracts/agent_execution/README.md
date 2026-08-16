# Agent Execution Contract v1.0.0

本 Contract 表示一个 Workflow Run 中某个正式 Agent 角色的一次 execution attempt。它不表示完整 Workflow，也不内嵌 Task、Context、Prompt、模型响应或 Artifact 内容。

## 身份

`execution_id` 是稳定引用。`execution_key` 由以下 UTF-8 文本计算 SHA-256，并添加 `EXK-` 前缀：

```text
v1
<run_id>
<agent_role>
<task_id-or-dash>
<attempt>
```

Coordinator 无 Task 时使用 `-`；Specialist 使用真实 Task ID。Retry 必须使用新的 `execution_id`、`attempt + 1` 和新 key，不能改写失败 attempt。

## 角色和结果

正式角色为 `coordinator`、`quality`、`production`、`sla`、`risk`。Specialist 必须引用 Task；Coordinator 可以从 Run 入口直接启动。成功 execution 只携带结构化结果引用，失败 execution 只携带失败分类，两者互斥。

## 使用

```python
from contracts.agent_execution.validator import validate_execution

validate_execution(payload)
```

Validator 会先拒绝不支持版本和严格 Schema 错误，再检查 key、Task、时间和引用不变量。`classify_execution_relation` 可区分 identical duplicate、相邻 revision、conflicting duplicate 和 distinct execution，但不能替代后续数据库唯一约束、乐观锁或状态事务。
