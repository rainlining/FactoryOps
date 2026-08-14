# Kafka Outbox Publisher 本地实验

本实验用于直观看到 FactoryOps 的 Outbox Publisher 如何把 MySQL 中的待发布事件写入 Kafka。Kafbat UI 只用于本地观察和学习，不属于生产运行时。

## 1. 启动 Kafka 与 Kafbat UI

在仓库根目录执行：

```powershell
docker compose -f infra/kafka/compose.yml up -d
docker compose -f infra/kafka/compose.yml ps
```

打开 `http://localhost:8090`，选择 `factoryops-local` 集群。Topic `factoryops.quality.incident.v1` 应有 3 个 Partition（分区）。Broker 已关闭自动建 Topic；Topic 由 `kafka-init` 显式创建。

## 2. 在 UI 中观察什么

进入 Topic 的 Messages 页面后，可以检查：

- Key：应等于 Outbox 保存的 `message_key`；
- Value：应是 Outbox 保存的 canonical payload（规范化载荷）原始 UTF-8 字节；
- Partition 和 Offset：Publisher 成功日志会记录这两个 Kafka 确认证据；
- 相同 Key：Kafka 会将它们路由到同一 Partition，但不会自动消除重复消息。

本 Change 没有 Consumer（消费者）。Publisher 的责任到 Kafka 确认消息为止；后续 Change `consume-quality-incident-events-idempotently` 才会增加订阅与消费，并通过 `event_id` 处理 at-least-once（至少一次投递）带来的重复。

## 3. 运行真实 Kafka 测试

```powershell
cd backend/business-service
mvn "-Dit.test=KafkaOutboxEventSenderIT" verify
mvn "-Dit.test=OutboxKafkaPublicationIT" verify
```

第一项验证原始 Key/Payload、Partition/Offset 以及不存在 Topic 时失败。第二项复现：Kafka 已接收消息，但数据库 `PENDING → PUBLISHED` 更新失败；下一轮再次发布同一个 `event_id`，因此 Kafka 中会出现 Key/Payload 相同但 Offset 不同的两条记录。

## 4. 可选的手工消息实验

进入 Kafka 容器后可使用官方 CLI：

```powershell
docker compose -f infra/kafka/compose.yml exec kafka /opt/kafka/bin/kafka-console-producer.sh --bootstrap-server kafka:9092 --topic factoryops.quality.incident.v1 --property parse.key=true --property key.separator=:
```

输入一行：

```text
QI-learning:{"event_id":"EVT-learning","event_type":"quality.incident.opened"}
```

然后在 Kafbat UI 中刷新 Messages。这个手工消息不是合法 FactoryOps 业务事件，只用于学习 Kafka UI 和 Key/Value；不要把它用于业务 Contract 验收。

## 5. 停止与清理

```powershell
docker compose -f infra/kafka/compose.yml down
```

本 Compose 未挂载 Kafka 数据卷，删除容器后本地实验消息不可恢复。
