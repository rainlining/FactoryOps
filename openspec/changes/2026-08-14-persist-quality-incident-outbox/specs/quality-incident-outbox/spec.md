# Quality Incident Outbox 规格增量

## 新增需求

### Requirement: 新 Incident 与 Outbox 必须原子成立

异常 Result 首次创建 OPEN Incident 时，系统必须在同一个 MySQL 事务中保存唯一的 `quality.incident.opened` Outbox。任一步失败时，Inspection 完成、Result、Incident 和 Outbox 必须全部回滚。

### Requirement: Outbox 必须保存不可变的完整事件

Outbox 必须保存 event ID、aggregate、event type、contract version、topic、message key、occurred_at 和完整 canonical JSON。发布或 replay 不得查询当前业务状态后重建事件。

### Requirement: 同一业务事实必须只有一个 Outbox

`event_id` 必须唯一；`aggregate_type + aggregate_id + event_type` 也必须唯一。相同身份和内容视为幂等，身份相同但路由、时间或 canonical payload 不同必须作为数据完整性冲突失败。

### Requirement: Result replay 不得创建第二个 Outbox

相同 Result 的顺序重放或并发败者读取胜者时，必须核对已有 Incident 和已有 Outbox。内容一致时返回 REPLAYED；Outbox 缺失或冲突时不得返回成功。

### Requirement: 已有 Incident 必须迁移回填

数据库迁移必须为所有已有 OPEN Incident 生成唯一 PENDING Outbox，保留 Incident 原 `created_at` 作为 `occurred_at`。回填事件必须符合冻结的 v1.0 Contract，并与 Java 新写入路径生成相同的 canonical JSON。

### Requirement: Outbox 必须保留原始 canonical 文本

payload 必须以保持原始文本的列存储，并由数据库验证为合法 JSON。Producer 后续必须逐字发布已保存的 payload，不得依赖 MySQL JSON 重新序列化。

### Requirement: 本 Change 只创建 PENDING 状态

新建和回填 Outbox 的状态必须为 PENDING，attempt count 为 0，available_at 等于 Outbox created_at，published_at 和 last_error 为空。Incident created_at 只映射到事件 occurred_at；历史回填的 Outbox created_at 表示实际迁移写入时间。本 Change 不实现状态领取或发布更新。

### Requirement: Outbox 必须提供稳定待发布顺序

数据库必须为后续 Producer 提供按 status、available_at、created_at、event_id 查询的索引，但本 Change 不定义并发领取或锁语义。
