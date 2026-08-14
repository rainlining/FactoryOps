# Review Handoff：2026-08-14-publish-outbox-events-to-kafka

## 元数据

- `learning_level`: `deep`
- `status`: `completed`
- `branch`: `codex/publish-outbox-events-to-kafka`
- `worktree`: `C:\Users\小霖\Desktop\work\project2\FactoryOps\.worktrees\publish-outbox-events-to-kafka`
- `base_commit`: `953d7791fb3c843b7aea68399725fbf4078f5eac`
- `implementation_head_before_handoff`: `a3ce454`
- Review 时以 feature branch 最新提交为准。

## 已实现范围

- 在现有 Business Service 内增加默认关闭的 Outbox Publisher 模块。
- 批量查询到期 `PENDING` 事件，但逐条执行 Kafka send → ack → 条件状态更新。
- 直接发送数据库保存的 Topic、Key 和 payload UTF-8 字节。
- 增加真实 Kafka/MySQL 自动化测试与 at-least-once 重复窗口测试。
- 增加单节点 KRaft Kafka、显式 Topic 初始化、Kafbat UI 和中文实验文档。

明确不包含：Kafka Consumer、多实例 Claim/Lease、retry/backoff、DLQ、Agent Runtime、修改业务事件 Contract。

## 关键设计决定

- Kafka 网络调用不放入 MySQL 事务；数据库只对单条条件状态更新使用短事务。
- Kafka ack 成功不能与 MySQL 状态更新形成跨系统原子事务，因此接受 at-least-once，并把最终去重责任留给 Consumer。
- Publisher 默认 `enabled=false`，当前部署只能启用一个实例；代码没有伪造多实例安全保证。
- Broker 关闭自动建 Topic；学习环境显式创建 3 Partition Topic。

## 建议阅读顺序与真实调用链

1. `ScheduledOutboxPublisher.runOnce`：定时入口和批次摘要日志。
2. `OutboxEventJdbcRepository.findPublishable`：筛选、数据库当前时间、稳定排序和批量上限。
3. `OutboxPublicationService.publish`：逐条编排、继续处理后续事件、成功与失败日志。
4. `KafkaOutboxEventSender.send`：构造 ProducerRecord、等待 acknowledgement、取得 Partition/Offset。
5. `OutboxEventJdbcRepository.markPublished`：条件更新、数据库时间和 affected-row 检查。
6. `OutboxPublisherConfiguration` 与 `application.yml`：默认关闭、Producer ack/idempotence/timeout。
7. `KafkaOutboxEventSenderIT`、`OutboxPublisherRepositoryIT`、`OutboxKafkaPublicationIT`：传输、持久化和重复窗口证据。
8. `infra/kafka/compose.yml` 与 `docs/learning/kafka-outbox-publisher-lab.md`：可视化学习环境。

成功链：Poller → 查询 PENDING → Publication Service → Kafka Sender → Broker ack（Partition/Offset）→ 条件更新 PUBLISHED → 成功/轮次日志。

主要失败链：

- Kafka 发送或等待 ack 失败：不更新数据库，事件保持 PENDING，记录失败并继续下一条。
- Kafka 已 ack、数据库标记失败：事件仍为 PENDING，下一轮再次发布，产生相同 event/key/payload、不同 Offset 的合法重复。
- 条件更新影响 0 行：抛出 `OutboxPublicationStateException`，不得误报成功。

## 验证与限制

完整命令、数量和证据见 `verification.md`。当前结果为 Java 24 unit + 38 integration、Python 35 Contract 全部通过；Compose、Topic 3 分区与 Kafbat UI health 已实测。验证后已执行 `docker compose down`。

剩余风险：单实例仅靠部署纪律；没有 retry/backoff、DLQ 和 Consumer 幂等；本地 UI 无生产认证。

## Review/Learning 任务

Owner 修改：在每轮摘要日志中增加 `last_successful_offset`，仅当本轮至少成功一条时出现；不得修改 Outbox 表或 payload，需增加日志断言。

Failure/debug exercise：注入 Kafka ack 成功后数据库标记失败，确认 MySQL 保持 PENDING；复位后再次运行，观察 Kafka 中相同 Key/Payload、不同 Offset 的两条消息和最终 PUBLISHED。自动化基线见 `OutboxKafkaPublicationIT`，Review 会话应完成可观察实验。

Learning Gate 已由独立 Review/Learning 会话完成，项目所有者已接受最终 diff 并批准归档。

## Review 会话恢复

```powershell
cd C:\Users\小霖\Desktop\work\project2\FactoryOps\.worktrees\publish-outbox-events-to-kafka
git status --short
git branch --show-current
git log --oneline 953d779..HEAD
```

Review 会话接手后，当前实现会话不得再并发修改此 worktree。
