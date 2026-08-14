# Change 提案：2026-08-14-publish-outbox-events-to-kafka

## 元数据

- `change_id`: `2026-08-14-publish-outbox-events-to-kafka`
- `status`: `proposed`
- `learning_level`: `deep`
- `depends_on`: `[2026-08-14-define-quality-incident-opened-event-contract, 2026-08-14-persist-quality-incident-outbox]`
- `spec_refs`: `[quality-incident-opened-event-contract, quality-incident-outbox]`
- `review_session`: `pending`

## 为什么要做

Business Service 已能在创建 OPEN Quality Incident 的同一 MySQL 事务中保存 PENDING Outbox，但事件尚未进入 Kafka。若没有独立 Publisher，Agent World 无法订阅已经成立的质量异常事实，Outbox 也会永久积压。

本 Change 建立第一个 Kafka Producer 发布链：单实例 Publisher 轮询 PENDING Outbox，逐条发送已保存的 topic、key 和 canonical payload，并且只在 Kafka broker acknowledgement 成功后把该行条件更新为 PUBLISHED。

## 范围

- 在现有 Java Business Service 内新增独立 `outbox.publisher` 模块。
- 使用固定延迟、稳定顺序和可配置 batch size 查询到期 PENDING Outbox。
- 使用 `acks=all`、Producer idempotence、明确 delivery timeout 和禁用 Topic 自动创建。
- 逐事件发送、等待 acknowledgement，并以短 MySQL 事务条件更新 PUBLISHED。
- 失败事件保持 PENDING；当前轮继续处理后续事件。
- 使用真实 Kafka Testcontainers 验证 topic、key、payload bytes、partition、offset 和状态更新。
- 本地 Docker Compose 增加单节点 KRaft Kafka、显式 Topic 初始化与 Kafbat UI。
- 提供中文 Kafka Learning Lab。

## 非目标

- Kafka Consumer、Consumer Group offset 提交与消费幂等。
- Agent Runtime、Coordinator Run 或任何 Agent Workflow。
- 多 Publisher 领取、owner、lease、`SKIP LOCKED` 或分布式锁。
- retry backoff、永久 FAILED、dead-letter 或人工恢复流程。
- Prometheus 指标、告警和 Consumer Lag 监控。
- 修改冻结的事件 Contract 或重新序列化 Outbox payload。
- exactly-once 保证。

## 学习等级理由

这是项目第一次真实实现 Kafka Producer、broker acknowledgement、partition/offset、Producer 会话内幂等和跨 MySQL/Kafka 的 at-least-once 重复窗口。它引入新的传输、超时、恢复与失败语义，因此为 `deep`，不能因已经学习过 Outbox 而降级。

后续 `consume-quality-incident-events-idempotently` 仍会因 Consumer offset、at-least-once redelivery、幂等登记和 Agent World 入口的新语义保持 `deep`。

