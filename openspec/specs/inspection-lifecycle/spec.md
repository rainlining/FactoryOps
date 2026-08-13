# Inspection Lifecycle 规格

## 需求

### Requirement: 创建具有确定输入身份的 Inspection

系统必须通过 `POST /api/v1/inspections` 创建 `PENDING` Inspection。输入必须包含非空 `inspection_id`、合法 URI `image_uri` 和 64 位小写十六进制 `sha256`，且不得包含未知字段。

相同 `inspection_id` 和相同图片身份的重复创建必须返回 200、`replayed=true` 并保持原状态与时间；相同 ID、不同图片身份必须返回 409 `inspection_identity_conflict`，不得覆盖原记录。

### Requirement: 查询 Inspection 当前状态

系统必须通过 `GET /api/v1/inspections/{inspection_id}` 返回输入身份、状态、创建时间、完成时间和已保存 Result 数量 `result_count`；不存在时返回 404 `inspection_not_found`。无 Result、一份 Result 和两份 Result 时，数量必须分别为 0、1 和 2。

### Requirement: 合法 Result 原子完成 Inspection

Vision Result 必须引用已存在且原始 `inspection_id`、`image_uri`、`sha256` 均匹配的 Inspection。新 Result 插入与 `PENDING → COMPLETED` 必须在同一事务提交；不存在或不匹配时返回 422 且 Result 不入库。

### Requirement: 多 Result 不覆盖首次完成时间

同一 Inspection 可以保存多个不同 `result_id`。并发时只有一个事务可以执行首次状态迁移，其他合法 Result 仍可提交，但不得覆盖 `completed_at`。

### Requirement: 数据库约束与历史迁移

MySQL 必须以外键保证 Result 父 Inspection 存在，并以约束保证 PENDING 的完成时间为空、COMPLETED 的完成时间非空。V2 必须从历史 canonical payload 回填 COMPLETED Inspection；同一 Inspection 的历史图片身份冲突时迁移必须失败。
