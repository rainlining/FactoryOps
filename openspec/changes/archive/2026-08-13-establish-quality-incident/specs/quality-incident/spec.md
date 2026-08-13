# Quality Incident 规格增量

## 新增需求

### Requirement: 合法异常 Result 必须原子创建唯一 OPEN Incident

当通过 Vision Contract 校验的 Result 满足 `observation.is_anomaly == true` 时，系统必须在保存 Result 和完成 Inspection 的同一 MySQL 事务中创建一个 `OPEN` Quality Incident。任一步骤失败必须使 Result、Inspection Completion 和 Incident 一起回滚。正常 Result 不得创建 Incident。

#### Scenario: Incident 写入失败

- **Given** 一个 PENDING Inspection 和一个合法异常 Result
- **When** Incident INSERT 被注入数据库失败
- **Then** 请求失败
- **And** Result 不存在
- **And** Inspection 保持 PENDING 且 `completed_at` 为空
- **And** Incident 不存在

### Requirement: 一个 Result 最多对应一个 Incident

Incident ID 必须为 `QI-` 加大写完整 SHA-256 十六进制摘要，摘要输入为 `factoryops:quality-incident:v1:result:<result_id>`。系统必须同时以 Incident ID 唯一键和 Result 引用唯一键保护一对一关系。

#### Scenario: 异常 Result 重放

- **Given** 一个异常 Result 已创建对应 Incident
- **When** 完全相同 Result 再次提交
- **Then** Result disposition 为 REPLAYED
- **And** 返回与首次相同的 `incident_id`
- **And** 数据库仍只有一个 Incident

### Requirement: Incident 必须保存完整且一致的证据引用

Incident 必须保存非空 `batch_id`、`inspection_id`、`result_id`，Java 与数据库约束必须保证它们属于同一条 Batch → Inspection → Result 证据链。Incident 不得复制 anomaly score、threshold、model 或 Artifact 内容。

### Requirement: Incident 来源不改变登记规则

fake、recorded 和 vision-service 来源的合法异常 Result 必须使用同一 Incident 创建规则；来源通过不可变 Result 引用追溯。

### Requirement: Incident Schema 和状态必须版本化

本 Change 生成的 Incident 必须声明 `incident_schema_version = "1.0"` 且状态只能为 `OPEN`。本 Change 不得提供状态迁移命令。

### Requirement: 支持单个 Incident 查询

系统必须通过 `GET /api/v1/quality-incidents/{incident_id}` 返回 Incident 自身快照，不展开关联资源。不存在时必须返回 404、错误码 `quality_incident_not_found` 和路径 `$.incident_id`。

### Requirement: 历史异常 Result 必须补建 Incident

V4 必须为全部历史异常 Result 使用同一派生 ID 规则补建 Incident，`created_at` 必须继承 Result 创建时间。历史正常 Result 不得产生 Incident，关系不一致时迁移必须失败。

### Requirement: Incident 创建不得自动改变 Batch 状态

创建 Incident 后，关联 Batch 必须保持创建前状态；HOLD 必须继续通过独立 Batch 命令执行。

## 修改需求

### Requirement: Result Intake 返回 Incident 导航信息

`POST /api/v1/inspection-results` 的响应必须增加可空 `incident_id`。异常 Result 首次创建和 replay 均返回稳定 ID；正常 Result 首次创建和 replay 均返回 `null`；identity conflict 不得创建 Incident。
