# FactoryOps 项目说明书（V0.2 Multi-Agent Architecture）

> 项目暂定名：**FactoryOps — Visual Quality Incident Multi-Agent System**  
> 中文名：**面向工业视觉质检异常的多智能体生产处置系统**  
> 文档版本：V0.2  
> 当前阶段：项目总纲 / Multi-Agent 架构冻结  
> 当前核心数据：MVTec AD 2 — Sheet Metal  
> 当前产品形态：**Multi-Agent 为正式系统形态，Single Agent 仅作为实验 Baseline**

---

# 1. 项目摘要

FactoryOps 是一个面向制造业视觉质检异常处置场景的 Multi-Agent 后端系统。

项目不以“识别缺陷”为终点，而以：

> **视觉检测发现异常后，系统如何结合质量、生产、订单、SLA 和风险策略，形成可执行、可审计、可恢复的业务处置方案**

作为核心问题。

当前 V1 以金属板材（Sheet Metal）视觉质检为入口。

系统完成：

```text
工业产品图片
    ↓
视觉异常检测
    ↓
质量异常事件
    ↓
Multi-Agent 协同分析
    ↓
业务决策
    ↓
权限 / 风险检查
    ↓
执行或人工审批
    ↓
状态更新
    ↓
Trace / Replay / Evaluation
```

最终系统不是一个聊天机器人，也不是一个简单的工业 RAG，而是一个具有：

- 明确业务状态；
- 异步事件；
- 多 Agent 协作；
- Tool Calling；
- Prompt / Context Engineering；
- 权限与审批；
- Checkpoint / Resume / Replay；
- 客观 Scenario Benchmark；
- 业务 KPI；
- 后端工程能力；

的完整 Agent System。

---

# 2. 项目解决的现实问题

## 2.1 现实业务背景

制造企业通常已经拥有：

- ERP
- MES
- QMS
- SCADA
- CMMS
- APS
- 视觉质检系统

这些系统分别保存订单、批次、生产、质量、设备和调度信息。

因此，本项目不试图重新实现：

```text
完整 MES
完整 QMS
完整 ERP
工业控制系统
```

本项目关注的是：

> **生产现场出现异常之后，如何快速完成跨系统状态整合和业务决策。**

---

## 2.2 以视觉质检异常为例

视觉模型检测出：

```json
{
  "is_anomaly": true,
  "anomaly_score": 0.93
}
```

这只能回答：

> 当前产品是否可能有缺陷？

但企业真正需要继续回答：

```text
是否直接报废当前产品？
是否需要二次复检？
是否只隔离当前产品？
是否冻结整个批次？
是否已经出现连续缺陷？
是否需要停线？
是否需要升级人工？
停止生产会造成多少业务损失？
当前订单是否临近 SLA？
当前动作是否符合质量和生产政策？
```

这些问题不再是纯视觉问题，而是跨业务域决策问题。

FactoryOps 解决的正是这一层。

---

# 3. 为什么需要 Agent

## 3.1 不需要 Agent 的情况

确定性逻辑仍由普通代码和规则实现。

例如：

```python
if emergency_stop_signal:
    stop_machine()
```

或者：

```python
if batch_status == "released":
    reject_duplicate_release()
```

这类逻辑不应该交给 LLM。

---

## 3.2 Agent 适合处理的问题

Agent 负责处理：

```text
信息不完整
+
业务状态分散
+
多个目标冲突
+
需要动态调用不同工具
+
长尾场景难以穷举
+
需要根据上下文调整决策
```

例如：

```text
当前视觉异常分数 = 0.58
模型置信度一般

当前订单：
高优先级
距离 deadline 只有 20 分钟

当前批次：
过去 200 件均正常

当前资源：
人工复检可立即执行

停线成本：
较高
```

此时系统不应简单写成：

```text
if anomaly_score > 0.5:
    stop_line
```

而应动态决定：

```text
RECHECK
```

并进一步获取证据后再做决策。

---

# 4. 为什么采用 Multi-Agent

本项目正式产品形态直接采用 Multi-Agent。

原因不是“Multi-Agent 更先进”，而是当前业务天然存在不同目标：

```text
Quality
→ 保证产品质量

Production
→ 保证生产连续性

SLA / Business
→ 控制延期与业务成本

Risk / Policy
→ 保证动作合法、安全、可审批
```

这些目标经常冲突。

因此，系统采用：

> **Supervisor / Coordinator + 专业 Agent**

的架构。

需要强调：

> Multi-Agent 的价值仍必须通过实验验证。

因此 Single Agent 会保留为 Baseline，但不作为正式产品形态。

---

# 5. Multi-Agent 总体架构

正式角色固定为：

```text
                     Incident Coordinator
                             │
        ┌────────────────────┼────────────────────┐
        ▼                    ▼                    ▼
 Quality Agent       Production Agent       SLA Agent
        │                    │                    │
        └────────────────────┼────────────────────┘
                             ▼
                    Decision Fusion
                             │
                             ▼
                    Risk / Policy Agent
                             │
                   ┌─────────┴─────────┐
                   ▼                   ▼
              Auto Execute         Approval
                                       │
                                       ▼
                                    Execute
```

当前正式 Agent：

1. Incident Coordinator Agent
2. Quality Agent
3. Production Agent
4. SLA / Business Agent
5. Risk / Policy Agent

---

# 6. Agent 1 — Incident Coordinator Agent

Coordinator 是整个 Incident Workflow 的 Owner。

它不负责专业判断，而负责：

- 创建 Incident；
- 加载初始 Context；
- 拆分专业任务；
- 并行调度专业 Agent；
- 汇总结构化结论；
- 判断是否缺少证据；
- 发起补充 Tool Call；
- 做最终 Decision Fusion；
- 提交 Risk / Policy 检查；
- 进入执行或审批流程；
- 观察执行结果；
- 决定完成、重试、暂停或失败。

---

## 6.1 Coordinator 不应该做的事

Coordinator 不直接：

- 判断视觉缺陷；
- 计算生产成本；
- 自己查询所有数据库；
- 直接操作业务表；
- 绕过 Risk Agent；
- 直接控制工业设备。

---

# 7. Agent 2 — Quality Agent

Quality Agent 负责质量专业判断。

输入主要包括：

- Vision Inspection Result；
- 当前 Batch；
- 最近质检历史；
- 质量策略；
- 相似 Incident；
- 当前产品信息。

它回答：

```text
当前产品是否应该放行？
是否需要复检？
是否应拒绝当前产品？
是否出现连续缺陷？
是否需要 HOLD_BATCH？
是否应升级质量工程师？
```

---

## 7.1 Quality Agent 输出

建议输出结构：

```json
{
  "agent": "quality",
  "severity": "HIGH",
  "recommendation": "HOLD_BATCH",
  "confidence": 0.91,
  "evidence_refs": [
    "inspection:731",
    "batch:B17"
  ],
  "reason_codes": [
    "CONSECUTIVE_DEFECTS",
    "HIGH_ANOMALY_CONFIDENCE"
  ]
}
```

---

# 8. Agent 3 — Production Agent

Production Agent 负责分析：

> 执行某个质量动作后，对生产造成什么影响？

输入主要包括：

- 当前订单；
- 当前 Batch；
- 产线状态；
- 当前产量；
- 预计停线时间；
- 生产能力；
- 当前 WIP；
- 订单剩余量。

它回答：

```text
如果 HOLD_BATCH 会发生什么？
如果 STOP_LINE 会发生什么？
订单是否延期？
预计停线多久？
是否能够继续当前生产？
```

---

## 8.1 Production Agent 输出示例

```json
{
  "agent": "production",
  "recommended_action": "CONTINUE_LINE",
  "estimated_delay_minutes": 0,
  "estimated_downtime_minutes": 0,
  "affected_orders": [],
  "confidence": 0.88
}
```

---

# 9. Agent 4 — SLA / Business Agent

SLA Agent 负责业务影响分析。

输入：

- Customer；
- Order；
- SLA；
- Deadline；
- Penalty；
- Scrap Cost；
- Recheck Cost；
- Hold Cost；
- Downtime Cost。

它回答：

```text
不同处置方案的业务成本是多少？
哪个订单最敏感？
是否可能产生 SLA 违约？
Defect Escape 的风险成本是多少？
```

---

## 9.1 输出示例

```json
{
  "agent": "sla",
  "recommended_action": "HOLD_BATCH",
  "expected_cost": 120.0,
  "alternative_costs": {
    "RECHECK": 20.0,
    "STOP_LINE": 430.0,
    "PASS_IF_DEFECT": 2000.0
  }
}
```

---

# 10. Agent 5 — Risk / Policy Agent

Risk Agent 是最终业务动作执行前的安全门。

它检查：

- 是否违反 Quality Policy；
- 是否违反 Production Policy；
- 是否超越 Agent 权限；
- 是否需要人工审批；
- 当前状态是否允许执行；
- 是否存在高风险副作用。

---

## 10.1 风险等级示例

```text
PASS
→ LOW

RECHECK
→ LOW

REJECT_ITEM
→ MEDIUM

HOLD_BATCH
→ MEDIUM

STOP_LINE
→ HIGH

RELEASE_HELD_BATCH
→ HIGH
```

---

## 10.2 输出示例

```json
{
  "allowed": true,
  "risk_level": "HIGH",
  "requires_human_approval": true,
  "policy_ids": [
    "QUALITY-POLICY-017",
    "PRODUCTION-STOP-003"
  ]
}
```

---

# 11. Vision Service 的定位

Vision Service 不是 Agent。

它是 Quality Agent 调用或依赖的专业感知服务。

输入：

```text
Sheet Metal Image
```

输出：

```json
{
  "image_id": "00731",
  "is_anomaly": true,
  "anomaly_score": 0.93,
  "mask_uri": "minio://...",
  "model_version": "vision-v1",
  "inference_ms": 37
}
```

原则：

> 专业感知模型负责“发生了什么”，Agent 负责“业务上应该怎么办”。

---

# 12. 当前视觉数据集

V1 使用：

> **MVTec AD 2 — Sheet Metal**

当前主要使用：

```text
train
validation
test_public
```

用途：

- train：视觉异常模型训练 / 正常模式学习；
- validation：参数和阈值验证；
- test_public：公开测试与本地 Benchmark。

---

# 13. Multi-Agent 完整业务运行链

一次正式 Incident：

```text
Sheet Metal Image
        ↓
Vision Service
        ↓
Inspection Result
        ↓
Java Quality Service
        ↓
MySQL Transaction
        ↓
Kafka: quality.anomaly_detected
        ↓
Agent Runtime
        ↓
Create Incident / Run
        ↓
Coordinator
        ↓
并行执行：
Quality Agent
Production Agent
SLA Agent
        ↓
Decision Fusion
        ↓
Need More Evidence?
    ┌───────┴───────┐
    ▼               ▼
   YES              NO
    │                │
 Tool Call        Risk Agent
    │                │
    └──────→ Re-evaluate
                     │
                     ▼
                Final Decision
                     │
            ┌────────┴────────┐
            ▼                 ▼
       Auto Execute        Approval
                               │
                               ▼
                            Execute
                               │
                               ▼
                     Java Business API
                               │
                               ▼
                         MySQL + Kafka
                               │
                               ▼
                            Observe
                               │
                               ▼
                         Complete Run
```

---

# 14. V1 动作空间

当前正式动作集合：

```text
PASS
RECHECK
REJECT_ITEM
HOLD_BATCH
STOP_LINE
ESCALATE
```

---

## 14.1 PASS

- 当前产品放行；
- 正常继续生产。

---

## 14.2 RECHECK

- 当前证据不足；
- 发起第二次视觉检测或人工复检。

---

## 14.3 REJECT_ITEM

- 当前产品判定为不合格；
- 隔离或报废当前产品；
- 不必停止整条产线。

---

## 14.4 HOLD_BATCH

- 当前批次暂停放行；
- 等待进一步质量判断；
- 不等价于直接停线。

---

## 14.5 STOP_LINE

- 停止当前生产线；
- 高风险动作；
- 默认需要严格权限或人工审批。

---

## 14.6 ESCALATE

- 升级给质量工程师 / 生产主管 / 人工审核流程。

---

# 15. Agent 间通信协议

Agent 之间原则上不传递自由文本聊天记录。

统一使用结构化 Contract。

示例：

```json
{
  "agent": "quality",
  "recommendation": "HOLD_BATCH",
  "severity": "HIGH",
  "confidence": 0.91,
  "evidence_refs": [
    "inspection:731",
    "batch:B17"
  ],
  "reason_codes": [
    "CONSECUTIVE_DEFECTS"
  ]
}
```

这样可以支持：

- schema validation；
- replay；
- debugging；
- evaluation；
- observability；
- contract versioning。

---

# 16. Context Engineering

不同 Agent 看到不同 Context。

---

## 16.1 Quality Agent Context

```text
System Prompt
Quality Role
Quality Policy

Current Inspection
Current Batch
Recent Inspection History
Similar Quality Incidents

Vision Result
Available Tools

Current Task
```

---

## 16.2 Production Agent Context

```text
System Prompt
Production Role

Current Batch
Current Order
Line State
Production Capacity
Current WIP
Estimated Downtime

Available Tools
Current Task
```

---

## 16.3 SLA Agent Context

```text
System Prompt
Business Role

Order
Customer
Deadline
Penalty
Scrap Cost
Recheck Cost
Hold Cost
Downtime Cost

Current Task
```

---

## 16.4 Risk Agent Context

```text
System Prompt
Risk Role

Proposed Decision
Agent Evidence Summary
Quality Policy
Production Policy
Permission Policy
Approval Policy
```

---

## 16.5 Coordinator Context

Coordinator 不读取所有 Agent 的完整 raw prompt。

主要读取：

```text
Incident Context
+
专业 Agent 的结构化结论
+
关键 Evidence
+
当前 Workflow State
```

---

# 17. Prompt Engineering

每个 Agent 的 Prompt 独立版本化。

至少包括：

- Role Prompt；
- Policy Prompt；
- Decision Protocol；
- Tool Instruction；
- Failure Policy；
- Escalation Policy；
- Output Schema；
- Prompt Version。

示例版本：

```text
quality-agent/v1.2
production-agent/v1.0
sla-agent/v1.1
risk-agent/v1.0
coordinator/v1.3
```

---

# 18. 后端总体架构

```text
                     Dashboard / Client
                             │
                             ▼
                     API Gateway / BFF
                             │
           ┌─────────────────┴─────────────────┐
           │                                   │
           ▼                                   ▼
  Java Business Backend                Python Agent Runtime
     Spring Boot                           FastAPI
           │                                   │
 Order / Batch / Quality              Coordinator / Agents
 Production / Approval                Context / Prompt
 Audit / Transaction                  Tools / Harness
           │                                   │
           └────────────── Kafka ──────────────┘
                             │
                ┌────────────┼────────────┐
                ▼            ▼            ▼
              MySQL        Redis        MinIO
```

---

# 19. Java / Spring Boot 职责

Java 作为确定性业务系统。

负责：

- Order Service；
- Batch Service；
- Product Service；
- Inspection Service；
- Quality Incident Service；
- Production Service；
- Approval Service；
- Audit Service；
- Business Transaction。

原则：

> Agent 不能直接修改 MySQL 业务表。

所有业务动作必须经过：

```text
Agent
↓
Java Business API
↓
Domain Validation
↓
Transaction
↓
MySQL
```

---

# 20. Python / FastAPI 职责

Python 负责：

- Agent Runtime；
- Multi-Agent Workflow；
- Model Adapter；
- Prompt Assembly；
- Context Engine；
- Tool Runtime；
- Vision Inference；
- Evaluation Harness；
- Agent Worker；
- Agent API。

---

# 21. Kafka 职责

Kafka 用于连接：

> **Business World ↔ Agent World**

不是为了让 Agent 相互聊天。

初步事件：

```text
inspection.completed
quality.anomaly_detected
quality.recheck_requested
quality.item_rejected
quality.batch_held
quality.batch_released
production.line_stop_requested
approval.requested
approval.completed
agent.decision_created
agent.run_failed
```

---

# 22. MySQL

业务数据：

```text
orders
customers
products
batches
inspections
quality_incidents
quality_actions
production_lines
approvals
audit_records
```

Agent 运行数据：

```text
agent_runs
agent_tasks
agent_decisions
model_calls
tool_invocations
prompt_versions
context_snapshots
checkpoints
```

---

# 23. Redis

Redis 用于：

- Incident 热状态；
- Agent Working State；
- Context Cache；
- Idempotency Key；
- Distributed Lock；
- Rate Limit；
- Temporary Tool Result；
- Run Lease；
- Short-lived Model Cache。

---

# 24. MinIO / Artifact Store

大内容不直接存 MySQL。

例如：

- 原始图片；
- Defect Mask；
- Context Artifact；
- Trace Artifact；
- Evaluation Report；
- 大模型 Raw Response；
- Replay Artifact。

---

# 25. Agent Harness

Harness 是项目的核心工程模块之一。

运行对象：

```text
Incident
Run
AgentTask
AgentRun
ModelCall
ToolInvocation
Decision
Command
Checkpoint
Artifact
```

关系：

```text
Incident
  └── Run
       ├── CoordinatorAgentRun
       ├── QualityAgentRun
       ├── ProductionAgentRun
       ├── SLAAgentRun
       └── RiskAgentRun
```

---

# 26. Harness 必须支持的能力

## 26.1 Timeout

覆盖：

- LLM timeout；
- Vision timeout；
- Tool timeout；
- Java API timeout。

---

## 26.2 Retry

仅重试明确可安全重试的操作。

禁止所有工具无条件自动重试。

---

## 26.3 Idempotency

业务副作用动作必须支持幂等。

例如：

```text
HOLD_BATCH
```

即使收到重复 Kafka 事件，也不能重复制造副作用。

---

## 26.4 Checkpoint

关键阶段建立检查点。

例如：

```text
Coordinator initialized
Quality completed
Production completed
SLA completed
Risk completed
Decision ready
Waiting approval
Execution completed
```

---

## 26.5 Resume

进程异常恢复后：

```text
不重复已经完成的 AgentTask
```

从最近可信 Checkpoint 继续。

---

## 26.6 Replay

同一个 Incident 可以使用：

```text
旧 Prompt
新 Prompt

旧 Model
新 Model

旧 Context Policy
新 Context Policy
```

重新运行并比较结果。

---

## 26.7 Cancellation

支持人工或系统取消 Run。

---

## 26.8 Human Approval

高风险动作进入：

```text
paused_waiting_approval
```

批准后继续 Workflow。

---

# 27. 可解释性

不把 LLM 自己生成的一段“理由”当作主要可解释性。

系统保存：

> **Decision Provenance**

示例：

```text
Decision ID
D-000231

Incident
INC-00037

Vision Evidence
anomaly_score = 0.93

Business State
Order = O102
Batch = B17
Recent Defects = 2

Quality Agent
HOLD_BATCH

Production Agent
CONTINUE_LINE

SLA Agent
Hold Cost = 120
Escape Risk = 2000

Risk Agent
Allowed
Approval = false

Final Decision
REJECT_ITEM
HOLD_BATCH
REQUEST_RECHECK

Tool Invocations
...

Prompt Version
...

Context Version
...

Execution Result
success
```

---

# 28. Evaluation 总体设计

FactoryOps 的评测单位不是 QA，而是：

> **Scenario / Episode**

完整体系：

```text
FactoryOps-Eval
│
├── Vision Benchmark
│
├── Agent Scenario Benchmark
│
├── Business KPI
│
└── Harness / Reliability Benchmark
```

---

# 29. Vision Benchmark

数据：

> MVTec AD 2 — Sheet Metal

指标：

- Image AUROC；
- Pixel AUROC；
- AUPRO；
- Precision；
- Recall；
- F1；
- FPR；
- FNR；
- P50/P95 inference latency。

---

# 30. Agent Scenario Benchmark

一个 Scenario 由以下内容组成：

```text
真实 Sheet Metal 图片
+
Order
+
Batch
+
Quality History
+
Line State
+
Cost Parameters
+
Available Resources
+
Event Sequence
```

---

# 31. Scenario 类型

V1 预计 200 个场景：

| 类型 | 数量 |
|---|---:|
| 全部正常 | 30 |
| 单个明显缺陷 | 30 |
| 单个轻微缺陷 | 25 |
| 连续缺陷 | 25 |
| 低置信度检测 | 25 |
| False Positive | 20 |
| False Negative | 20 |
| 高优先级订单 + 缺陷 | 15 |
| 复合异常 | 10 |
| **总计** | **200** |

---

# 32. Scenario 示例

```json
{
  "scenario_id": "quality_0042",
  "seed": 42,

  "order": {
    "order_id": "O-102",
    "priority": "normal",
    "quantity": 500,
    "deadline_minutes": 180
  },

  "batch": {
    "batch_id": "B-17",
    "produced": 238,
    "recent_defects": 1
  },

  "inspection": {
    "image_id": "sheet_metal_xxx",
    "ground_truth": "anomaly",
    "vision_score": 0.91
  },

  "resources": {
    "manual_recheck_available": true
  }
}
```

`ground_truth` 只允许 Evaluator 使用，不进入 Agent Context。

---

# 33. Ground Truth

业务决策不强制只有一个标准动作。

采用：

```text
业务约束
+
Required Outcome
+
Forbidden Outcome
+
Cost Model
```

例如：

```json
{
  "required_outcomes": [
    "defective_item_not_shipped"
  ],
  "allowed_actions": [
    "RECHECK",
    "REJECT_ITEM",
    "HOLD_BATCH",
    "STOP_LINE",
    "ESCALATE"
  ],
  "forbidden_actions": [
    "PASS"
  ]
}
```

---

# 34. Cost Model

初步成本项：

```text
Defect Escape Cost
False Reject Cost
Manual Recheck Cost
Batch Hold Cost
Production Downtime Cost
SLA Penalty
```

示意：

```text
漏放缺陷品：100
错误报废正常品：5
人工复检：2
错误冻结批次：30
停线：20 / minute
```

具体权重后续根据公开资料与实验敏感性分析确定。

---

# 35. Agent KPI

核心：

- Defect Escape Rate；
- False Reject Rate；
- Correct Escalation Rate；
- Unnecessary Stop Rate；
- Unsafe Action Rate；
- Human Intervention Rate；
- Mean Time To Decision；
- Decision Completion Rate。

---

# 36. Business KPI

核心：

- Total Quality Cost；
- Production Downtime；
- Scrap Cost；
- SLA Penalty；
- Defect Escape；
- Batch Hold Time；
- Incident Resolution Time。

---

# 37. Engineering KPI

核心：

- Tool Success Rate；
- Invalid Action Rate；
- Retry Success Rate；
- Checkpoint Recovery Rate；
- Duplicate Event Handling Accuracy；
- P50/P95 Decision Latency；
- Model Calls / Scenario；
- Tokens / Scenario；
- Context Tokens / Decision；
- Agent Runtime Failure Rate；
- Kafka Consumer Lag；
- API P95 Latency。

---

# 38. Baseline

虽然产品正式采用 Multi-Agent，但实验必须包含：

```text
B0 Rule-based

B1 Single Agent

B2 Multi-Agent
```

目的是回答：

> Multi-Agent 是否真的比 Single Agent 更有业务收益？

最终报告需要同时展示：

```text
效果
成本
Latency
Token
稳定性
```

---

# 39. Ablation

至少包括：

## 39.1 Multi-Agent Ablation

```text
Single Agent
vs
Multi-Agent
```

---

## 39.2 Context Ablation

```text
Full Context
vs
No History
vs
No Cost Context
vs
No Similar Incident
```

---

## 39.3 Vision Robustness

```text
Perfect Vision
vs
Noisy Vision
vs
False Positive
vs
False Negative
```

---

## 39.4 Harness Reliability

```text
Normal
vs
Tool Timeout
vs
Duplicate Kafka Event
vs
LLM Timeout
vs
Agent Crash
```

---

# 40. Docker 化

目标使用 Docker Compose 一键启动。

预期服务：

```text
business-service
agent-api
agent-worker
vision-service

mysql
redis
kafka
minio

prometheus
grafana
otel-collector
```

---

# 41. Observability

建议最终加入：

- OpenTelemetry；
- Prometheus；
- Grafana；
- Structured Logging；
- Distributed Trace。

观测内容：

```text
Incident Timeline
AgentRun Timeline
Model Latency
Tool Latency
Kafka Lag
Tokens
Cost
Context Size
Retry
Failure
Approval
```

---

# 42. 仓库结构建议

```text
factoryops/
│
├── services/
│   │
│   ├── business-service/
│   │   ├── order/
│   │   ├── batch/
│   │   ├── quality/
│   │   ├── production/
│   │   ├── approval/
│   │   └── audit/
│   │
│   ├── agent-service/
│   │   ├── runtime/
│   │   ├── coordinator/
│   │   ├── agents/
│   │   │   ├── quality/
│   │   │   ├── production/
│   │   │   ├── sla/
│   │   │   └── risk/
│   │   ├── context/
│   │   ├── prompts/
│   │   ├── tools/
│   │   ├── harness/
│   │   └── model/
│   │
│   └── vision-service/
│       ├── models/
│       ├── inference/
│       └── api/
│
├── evals/
│   ├── datasets/
│   ├── scenarios/
│   ├── generators/
│   ├── baselines/
│   ├── metrics/
│   └── reports/
│
├── contracts/
│   ├── events/
│   ├── agent_outputs/
│   └── api/
│
├── infra/
│   ├── mysql/
│   ├── redis/
│   ├── kafka/
│   ├── minio/
│   ├── prometheus/
│   └── grafana/
│
├── docker/
├── docs/
└── docker-compose.yml
```

---

# 43. 开发里程碑

## M0 — Evaluation First

完成：

- Scenario Schema；
- Cost Model；
- Evaluator；
- Rule Baseline；
- 初版 200 Scenario Generator。

---

## M1 — Vision Service

完成：

- Sheet Metal 数据整理；
- Vision Model；
- FastAPI；
- Vision Benchmark；
- 输出协议。

---

## M2 — Java Business Backend

完成：

- Order；
- Batch；
- Product；
- Inspection；
- Quality Incident；
- Approval；
- Audit；
- MySQL。

---

## M3 — Kafka Backbone

完成：

- Event Contract；
- Producer；
- Consumer；
- Outbox；
- 基础 Replay。

---

## M4 — Agent Harness

完成：

- Incident；
- Run；
- AgentRun；
- ModelCall；
- ToolInvocation；
- Decision；
- Trace；
- Checkpoint。

---

## M5 — 专业 Agents

完成：

- Quality Agent；
- Production Agent；
- SLA Agent；
- Risk Agent。

---

## M6 — Coordinator

完成：

- Task Dispatch；
- Parallel Execution；
- Decision Fusion；
- Need-more-evidence；
- Approval；
- Execute；
- Observe。

---

## M7 — Redis / Reliability

完成：

- Idempotency；
- Lock；
- Run Lease；
- Context Cache；
- Retry；
- Resume。

---

## M8 — Evaluation

完成：

```text
Rule
Single Agent
Multi-Agent
```

在 200 Scenario 上运行。

---

## M9 — Failure Injection

覆盖：

- Kafka Duplicate；
- Tool Timeout；
- Vision Timeout；
- LLM Timeout；
- Java API Failure；
- Agent Crash；
- Resume。

---

## M10 — Observability

完成：

- OpenTelemetry；
- Prometheus；
- Grafana；
- Trace Dashboard。

---

## M11 — Docker Delivery

目标：

```bash
docker compose up
```

可启动完整系统。

---

# 44. 最终 Demo

Demo 需要清楚展示：

```text
当前订单
当前批次
生产进度
最新 Sheet Metal 图片
Vision Result
```

发生：

```text
QUALITY INCIDENT
anomaly_score = 0.93
```

随后展示：

```text
Quality Agent
→ HOLD_BATCH

Production Agent
→ CONTINUE_LINE

SLA Agent
→ HOLD cost 120
→ escape risk 2000

Risk Agent
→ allowed
```

Coordinator：

```text
REJECT_ITEM
HOLD_BATCH
REQUEST_RECHECK
CONTINUE_LINE
```

右侧展示：

```text
Agent Trace
Tool Calls
Context
Tokens
Latency
Kafka Events
Decision Provenance
```

---

# 45. 项目技术栈

## Backend

- Java
- Spring Boot
- Python
- FastAPI
- MySQL
- Redis
- Kafka
- REST API
- Docker

## Agent

- Multi-Agent
- Supervisor / Coordinator
- Tool Calling
- Workflow
- Prompt Engineering
- Context Engineering
- Structured Output
- Human-in-the-loop
- Checkpoint / Resume / Replay

## AI

- Industrial Vision
- Anomaly Detection
- MVTec AD 2
- Sheet Metal

## Engineering

- Evaluation Harness
- Event-driven Architecture
- Idempotency
- Retry
- Failure Injection
- Distributed Trace
- Observability

---

# 46. 非目标

当前明确不做：

- 完整 MES；
- 完整 ERP；
- PLC 实时控制；
- ROS / Gazebo 大规模机器人系统；
- 通用聊天机器人；
- 单纯工业 RAG；
- Agent 直接写业务数据库；
- LLM 直接控制工业安全设备；
- 用 LLM Judge 作为主要业务评测指标；
- 为了技术栈而加入无业务意义的中间件。

---

# 47. 当前冻结结论

截至 V0.2：

1. 正式产品形态直接采用 Multi-Agent。
2. Single Agent 只作为 Baseline。
3. Agent 固定为 Coordinator + Quality + Production + SLA + Risk。
4. Vision Service 不是 Agent，而是专业 Tool / Service。
5. V1 只使用视觉模态。
6. 核心数据采用 MVTec AD 2 — Sheet Metal。
7. Agent Benchmark 采用 Scenario / Episode。
8. 业务正确性优先采用规则、约束、Simulator 和 Cost Model。
9. Agent 间使用结构化 Contract，不使用自由聊天记录。
10. Java 负责确定性业务系统。
11. Python 负责 Agent、AI 和 Evaluation。
12. Kafka 负责 Business World 与 Agent World 的事件连接。
13. MySQL 保存业务与 Agent 结构化状态。
14. Redis 负责热状态、幂等、锁、缓存和 Run Lease。
15. MinIO 保存大 Artifact。
16. 高风险动作必须经过权限和审批。
17. Harness 必须支持 Trace / Checkpoint / Resume / Replay。
18. 所有重要性能数据必须通过可复现实验得到。

---

# 48. 当前待设计问题

后续需要逐项讨论：

1. Sheet Metal 的具体 Vision Model。
2. Vision Output Schema 最终字段。
3. Order / Batch / Inspection / Incident 的领域模型。
4. Java Service 是否采用模块化单体还是多个微服务。
5. Kafka Event Schema。
6. MySQL Schema。
7. Agent Runtime 是否完全自研。
8. Coordinator 的 Workflow 状态机。
9. Agent Tool Catalog。
10. Context Assembly 规则。
11. Prompt Contract。
12. Cost Model 权重来源。
13. Scenario Generator 参数分布。
14. Evaluation Split。
15. Single Agent Baseline 具体实现。
16. Multi-Agent Parallelism 与并发控制。
17. Checkpoint 持久化策略。
18. Human Approval 状态机。
19. Dashboard 技术方案。
20. 最终部署是否扩展 Kubernetes。

---

# 49. 下一步设计顺序

建议按照以下顺序继续：

```text
P1 业务领域模型
↓
P2 Agent Runtime / Workflow
↓
P3 Tool & Contract
↓
P4 Context / Prompt
↓
P5 Evaluation Harness
↓
P6 Backend Architecture
↓
P7 Reliability / Recovery
↓
P8 Observability
↓
Implementation
```

---

# 50. 一句话项目说明

> **FactoryOps 是一个面向工业视觉质检异常的 Multi-Agent 生产处置系统：视觉模型发现 Sheet Metal 缺陷后，Quality、Production、SLA 和 Risk 等专业 Agent 会在 Coordinator 编排下综合质量、生产和业务约束，决定复检、报废、冻结批次、停线或升级人工，并通过 Kafka、MySQL、Redis、Java/FastAPI 后端和可恢复 Agent Harness 完成可靠执行与客观评测。**

