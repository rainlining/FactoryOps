# 技术设计：Transactional Outbox 持久化

## 1. 设计结论

采用应用层 Transactional Outbox，而不是事务提交后直发 Kafka，也不在当前阶段引入 Debezium/CDC。Java 在创建 Incident 的现有 MySQL READ COMMITTED 事务中生成并保存不可变事件；Kafka 发布留给独立 Change。

核心不变量：

```text
新 Incident 存在 ⇔ 对应的唯一 PENDING Outbox 存在
```

对于迁移前已有 Incident，该不变量由 Flyway 回填建立；普通运行时 replay 不负责静默修复缺失 Outbox。

## 2. 组件边界

- `InspectionResultIntakeService`：继续拥有最外层写事务与并发败者恢复路径。
- `QualityIncidentService`：负责 Incident 与对应 Outbox 成对成立，并在 replay 时核对现有 Outbox。
- `QualityIncidentOpenedEventFactory`：纯 Java 组件，从已成立 Incident 生成确定性事件和 canonical JSON，不访问数据库。
- `OutboxEventRepository`：保存和读取 Outbox，不发送 Kafka。
- Flyway migration：创建表、约束、索引并回填历史 Incident。

生产运行时不重复执行完整 JSON Schema。Event Factory 使用强类型输入；构建时 Contract Test 使用冻结 Schema 验证真实 Java 输出。Consumer 将来仍必须验证外部输入。

## 3. 数据流

### 3.1 新异常 Result

```text
HTTP Result intake
→ Contract validation
→ BEGIN READ COMMITTED
→ load Inspection
→ complete Inspection
→ insert Result
→ create OPEN Incident
→ Event Factory builds immutable event
→ insert PENDING Outbox
→ COMMIT
```

Event Factory 使用 Incident `created_at` 作为 `occurred_at`。若事件生成或 Outbox INSERT 失败，异常沿调用链向外传播，整个事务回滚。

### 3.2 相同 Result replay

找到已有 Result 且 payload hash 相同时，系统查找已有 Incident 和 Outbox，并核对 event ID、aggregate、event type、contract version、topic、message key、occurred_at 与 canonical payload。完全一致才返回 REPLAYED；缺失或冲突均失败，不新增第二条 Outbox。

### 3.3 并发相同 Result

胜者提交 Result、Incident 和 Outbox。败者的重复键异常使其整个事务回滚，然后进入现有 winner-read 路径，读取并核对胜者的三个对象。败者不得留下临时 Incident 或 Outbox。

### 3.4 历史回填

迁移从已有 OPEN Incident 生成确定性 event ID、原 occurred_at 与 canonical payload，插入 PENDING Outbox。回填必须使用与 Java 相同的字段集合、UTC 微秒格式、JSON escaping 和 key 排序，并由 V1→最新版本迁移测试逐项验证。

## 4. 数据模型

`outbox_events` 包含：

- `event_id VARCHAR(68)` 主键；
- aggregate type、ID hash 与 ID；
- event type、contract version、topic、message key；
- `occurred_at TIMESTAMP(6)`；
- `payload LONGTEXT` 与 `JSON_VALID` CHECK；
- status、attempt count、available_at、published_at、last_error、created_at。

`occurred_at` 是 Incident 成立的业务时间；`created_at` 是 Outbox 行实际写入的技术时间。历史回填不得改写 occurred_at，但其 created_at/available_at 使用迁移写入时间。后续 Producer 的延迟指标必须从这两个时间语义中明确选择，不能混用。

关键约束：

- event ID 主键；
- aggregate type + aggregate ID hash + event type 唯一；
- aggregate ID hash + ID 外键指向 Quality Incident；
- 表的事件信封字段可复用，但当前外键有意把本 Change 限定为 Quality Incident；未来支持其他 aggregate 时必须另行设计并迁移外键策略；
- status 只允许 PENDING/PUBLISHED；
- PENDING 必须没有 published_at，PUBLISHED 必须有 published_at；
- attempt count 非负；
- `(status, available_at, created_at, event_id)` 待发布索引。

本 Change 只插入 PENDING。表为未来事件复用，不把 `quality.incident.opened` 常量硬编码为整表唯一允许值。

## 5. 事件与存储语义

event ID 逐字遵循已生效 Contract：

```text
EVT- + UPPER_HEX(SHA-256(
  "factoryops:event:quality.incident.opened:v1:" + incident_id
))
```

payload 使用 `LONGTEXT`，因为 Outbox 保存的是以后要发布的不可变 canonical 文本，而不仅是语义相同的 JSON 对象。MySQL JSON 类型可能改变文本表现，不能作为原始发布字节来源。

Event Factory 不包含 anomaly score、threshold、model、Artifact、Result origin、当前 Batch 状态或 Evaluation ground truth。

## 6. 状态与所有权

初始状态：

- status = PENDING；
- attempt_count = 0；
- available_at = Outbox created_at；
- published_at = NULL；
- last_error = NULL。

PUBLISHED 状态只为后续 Producer 预留。本 Change 不实现领取、更新、retry、lease、永久 FAILED 或死信，因此不声称解决发布并发。

## 7. 失败路径

- Event Factory 失败：整个业务事务回滚。
- Outbox 约束或 INSERT 失败：Inspection、Result、Incident 与 Outbox 全回滚。
- event ID 或 aggregate 唯一键冲突：读取已有记录并精确核对；不同内容不能吞掉异常。
- Incident 有而 Outbox 无：完整性错误。
- 回填 payload 不符合 Contract：迁移测试失败，不能发布该版本。
- 并发败者找不到胜者 Outbox：失败，不返回伪 REPLAYED。

## 8. 测试与证据

- Factory 单元测试：ID、时间、字段、canonical JSON。
- Java→Schema Contract Test：真实 Java 输出通过冻结 v1.0 Schema。
- Repository/MySQL：主键、aggregate 唯一键、外键、JSON_VALID、状态 CHECK、精确文本读取。
- HTTP/MySQL：新建、顺序 replay、并发 replay 和查询证据。
- Migration：V1→最新历史回填数量、时间、身份和 payload。
- 原子回滚：注入非法 Outbox status，验证四个对象全部回滚。
- 回归：既有 Vision Contract、Result、Inspection、Batch 与 Incident 行为不变。

## 9. 被放弃的方案

- 提交后直接发 Kafka：存在双写窗口。
- 当前引入 Debezium/CDC：增加部署复杂度并掩盖事务学习目标。
- Outbox 只保存 Incident ID：发布和 replay 会按当前状态重建，破坏不可变事实。
- MySQL JSON payload：不保证保留原始 canonical 文本。
- replay 时静默补 Outbox：掩盖迁移或数据损坏。
- 当前设计永久 FAILED、lease 或锁：其失败分类和并发模型属于 Producer Change。
