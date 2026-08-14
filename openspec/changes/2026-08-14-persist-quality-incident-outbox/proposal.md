# Change 提案：2026-08-14-persist-quality-incident-outbox

## 元数据

- `change_id`: `2026-08-14-persist-quality-incident-outbox`
- `status`: `learning-preflight-passed`
- `learning_level`: `deep`
- `depends_on`: `[2026-08-13-establish-quality-incident, 2026-08-14-define-quality-incident-opened-event-contract]`
- `spec_refs`: `[quality-incident, quality-incident-opened-event-contract]`
- `review_session`: `pending`

## 为什么要做

Quality Incident 已能在 MySQL 事务中成立，事件 Contract 也已冻结，但系统尚不能原子地记录“业务事实”和“等待发布的事件”。若数据库提交后直接调用 Kafka，会留下 Incident 已提交但事件丢失，或消息已发送但事务回滚的双写窗口。

本 Change 使用 Transactional Outbox：在创建 Incident 的同一 MySQL 事务中保存不可变的 `quality.incident.opened` 事件。它只关闭数据库一致性缺口，不连接 Kafka。

## 范围

- 新增通用 `outbox_events` 表、约束、发布状态字段和待发布查询索引。
- 为已有 OPEN Incident 回填唯一 PENDING Outbox。
- Java Event Factory 根据 Incident 生成确定性 event ID 与 canonical JSON。
- 新 Incident 与 Outbox 在现有 READ COMMITTED 写事务中原子提交。
- Result replay 和并发败者读取已有 Incident 时，核对已有 Outbox 的身份与内容。
- 提供 Domain、Contract、Repository、HTTP/MySQL、迁移、并发与回滚测试。

## 非目标

- Kafka broker、topic 创建、Producer、Consumer、offset 或 acknowledgement。
- Outbox 领取、lease、lock owner、并发发布、retry/backoff、永久 FAILED 或死信。
- Incident 状态迁移、Batch HOLD、Agent Runtime 或 Coordinator。
- 修改事件 Contract 或 Vision Contract。

## 学习等级理由

这是第一次实现 Transactional Outbox，新增数据库一致性语义、历史迁移、唯一性、事务回滚和并发重放失败模型，因此为 `deep`。后续 Producer 仍会因 Kafka acknowledgement、at-least-once 和并发领取的新语义保持 `deep`。

## 后续顺序

`persist-quality-incident-outbox` → `publish-outbox-events-to-kafka` → `consume-quality-incident-events-idempotently`。
