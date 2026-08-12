# Inspection Lifecycle 规格增量

## 新增需求

### Requirement: 创建具有确定输入身份的 Inspection

系统必须通过 `POST /api/v1/inspections` 创建 `PENDING` Inspection。输入必须包含非空 `inspection_id`、合法 URI `image_uri` 和 64 位小写十六进制 `sha256`，且不得包含未知字段。

#### Scenario: 首次创建
- **Given** 尚不存在的 Inspection 身份和合法输入
- **When** 创建 Inspection
- **Then** 返回 201、`replayed=false` 和 `status=PENDING`
- **And** `created_at` 使用应用 UTC Clock，`completed_at` 为 null

#### Scenario: 创建幂等重放
- **Given** 已存在相同 `inspection_id` 和完全相同图片身份
- **When** 再次创建
- **Then** 返回 200 和 `replayed=true`
- **And** 保持原状态和时间不变

#### Scenario: Inspection 身份冲突
- **Given** 已存在相同 `inspection_id` 但图片身份不同
- **When** 再次创建
- **Then** 返回 409 `inspection_identity_conflict`
- **And** 不覆盖原记录

### Requirement: 查询 Inspection 当前状态

系统必须通过 `GET /api/v1/inspections/{inspection_id}` 返回输入身份、状态、创建时间和完成时间；不存在时返回 404 `inspection_not_found`。

### Requirement: 合法 Result 原子完成 Inspection

Vision Result 必须引用已存在且原始 `inspection_id`、`image_uri`、`sha256` 均匹配的 Inspection。新 Result 插入与 `PENDING → COMPLETED` 必须在同一事务提交。

#### Scenario: 第一份结果完成任务
- **Given** 匹配的 PENDING Inspection
- **When** 提交合法且全新的 Result
- **Then** Result 被保存且 Inspection 变为 COMPLETED
- **And** `completed_at` 是 FactoryOps 首次接受结果的 UTC 时间

#### Scenario: 不存在的 Inspection
- **Given** Contract 合法但 `inspection_id` 不存在
- **When** 提交 Result
- **Then** 返回 422 `inspection_not_found`
- **And** Result 不入库

#### Scenario: 图片身份不匹配
- **Given** Inspection 存在但 Result 图片身份不同
- **When** 提交 Result
- **Then** 返回 422 `inspection_input_mismatch`
- **And** 同时不同时优先报告 `$.input.image_uri`，其次 `$.input.sha256`

### Requirement: 多 Result 不覆盖首次完成时间

同一 Inspection 可以保存多个不同 `result_id`。并发时只有一个事务可以执行首次状态迁移，其他合法 Result 仍可提交，但不得覆盖 `completed_at`。

### Requirement: 数据库阻止孤立 Result 与非法状态

MySQL 必须以外键保证 Result 父 Inspection 存在，并以约束保证 PENDING 的完成时间为空、COMPLETED 的完成时间非空。

### Requirement: V2 安全迁移历史 Result

迁移必须从历史 canonical payload 回填 COMPLETED Inspection；同一 `inspection_id` 的所有历史 Result 图片身份一致时只创建一个父实体，存在不同图片身份时迁移必须失败。

## 修改需求

### Requirement: Java API 接收 Contract 1.0

系统必须先完成 JSON、Vision Schema 和 Domain 校验，再在一个 READ COMMITTED 事务中验证 Inspection、保存 Result 并推进状态。既有 malformed、Contract issue、result replay/conflict 语义保持不变。
