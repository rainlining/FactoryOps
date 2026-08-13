# Change 设计：2026-08-13-establish-quality-incident

## 设计摘要

Quality Incident 是“异常需要持续处理”的业务问题单，不是 Vision Result 的副本。Result Intake 仍拥有最外层写事务，并显式调用 Quality Incident 应用服务，使 Result INSERT、Inspection Completion 和 Incident INSERT 共同提交或回滚。

## 边界与组件

- `InspectionResultIntake`：拥有完整写事务、Result 幂等分类和调用顺序。
- `QualityIncidentService`：依据已校验 `is_anomaly` 决定是否登记、派生 ID、处理创建/replay。
- `QualityIncidentRepository`：Incident SQL 和证据查询。
- `QualityIncident`：版本、OPEN 状态、身份和证据引用不变量。
- `QualityIncidentQueryService`：只读事务和后续派生查询组合点。
- `QualityIncidentController`：单体查询 HTTP 边界。

不得使用异步 Spring 事件或提交后监听器创建 Incident，因为它们无法满足当前原子事实要求。

## 数据流

### 异常首次创建

```text
HTTP Result → Contract Validator → 写事务
→ 锁定/验证 Inspection → INSERT Result → 完成 Inspection
→ QualityIncidentService → 派生 ID → 验证证据链 → INSERT Incident
→ COMMIT → CREATED + incident_id
```

### 正常 Result

保存 Result 并完成 Inspection，但跳过 Incident，返回 `incident_id = null`。

### Replay

canonical content 相同则不重写 Result 或 `completed_at`。异常 Result 查询原 Incident 并返回同一 ID；正常 Result 仍返回 `null`。内容变化继续返回 Result identity conflict。

## 身份与不变量

```text
incident_id = "QI-" + UPPER_HEX(
  SHA-256("factoryops:quality-incident:v1:result:" + result_id)
)
```

派生 ID 负责稳定导航和重放；`UNIQUE(result_id_hash, result_id)` 直接表达“一条 Result 最多一个 Incident”，两者不能互相替代。

Incident 只拥有 schema version、ID、OPEN 状态、证据引用和创建时间。模型观察字段继续由不可变 Result 拥有。

## Schema 与迁移

V4 新建 `quality_incidents`：

- hash + 原值形式的 Incident、Batch、Inspection、Result ID；
- `incident_schema_version` CHECK 仅允许 `1.0`；
- `status` CHECK 仅允许 `OPEN`；
- Incident ID 和 Result 引用唯一约束；
- 组合外键尽可能固化 Batch → Inspection → Result 关系；
- 所有引用非空。

迁移连接历史 Result、Inspection、Batch，只为异常 Result 补建 Incident，创建时间使用 Result `created_at`。迁移不得猜测或修补不一致关系。

## 事务、并发与失败

- 同一 Inspection 继续通过父行锁串行化完成与 Result 写入。
- 相同 Result 并发依靠现有 Result 唯一键分类，最终读取同一 Incident。
- Incident INSERT 或关系验证失败向外抛出，使最外层 TransactionTemplate 回滚。
- 本 Change 不在未知提交状态周围添加自动数据库 retry；调用方可以重放相同 Result。
- Incident 创建不调用 Batch HOLD，不改变 Batch 状态。

## HTTP Contract

- Result Intake 响应增加可空 `incident_id`。
- `GET /api/v1/quality-incidents/{incident_id}` 返回版本、ID、OPEN、三个证据 ID 和创建时间。
- 不存在返回 `404 quality_incident_not_found`，路径 `$.incident_id`。
- 不提供 Incident 列表或状态命令。

## 测试策略

- Domain：稳定派生 ID、不同输入、版本/状态和缺失证据。
- HTTP/MySQL：异常/正常、首次/replay/conflict、三种 origin、查询、404、Batch 不变、并发相同 Result。
- V4：历史异常回填、正常跳过、时间继承、CHECK/唯一键/组合外键、V1→V4。
- 原子故障：注入 Incident INSERT 失败，断言 Result=0、Incident=0、Inspection=PENDING 且无 `completed_at`。
- 完整 Java、Python Contract、diff 与 dataset scope 回归。

## 被放弃的方案

- 独立 Incident 创建 API：允许异常 Result 与问题单分离失败。
- Kafka Consumer 后建 Incident：Outbox/Kafka 尚未存在，当前无法闭合确定性业务链。
- 自动 HOLD：把登记异常与生产处置错误绑定。
- 复制 Result 摘要：形成两个事实来源。
- 完整 Incident 状态机：Coordinator、审批、权限尚未定义。
- Spring 领域事件：隐藏调用链或跨越事务提交边界。
