# Agent Task Contract v1.0.0

Task 是 Coordinator 在一个 Workflow Run 中分派给专业 Agent 的稳定工作要求。Task retry 不创建新 Task，而是在同一 Task 下创建新的 Agent Execution attempt。

`task_key` 为 `TAK-` 加以下 UTF-8 文本的 SHA-256 大写摘要：

```text
v1
<run_id>
<task_request_id>
```

正式映射：`QUALITY_ANALYSIS→quality`、`PRODUCTION_ANALYSIS→production`、`SLA_ANALYSIS→sla`、`RISK_ASSESSMENT→risk`。

Task 终态失败详情 `failure.message` 必须为 1 至 600 个字符；它保存简短、可审计的聚合失败说明，不承载完整 Execution 输出或大型诊断 Artifact。

```python
from contracts.agent_task.validator import validate_task

validate_task(payload)
```

Validator 不替代后续数据库唯一约束、依赖图检查、乐观锁或 retry policy。
