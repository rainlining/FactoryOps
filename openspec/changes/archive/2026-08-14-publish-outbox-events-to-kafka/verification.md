# 验证记录：2026-08-14-publish-outbox-events-to-kafka

- `status`: `completed`
- `baseline_python_contract_tests`: `35 passed`
- `baseline_java_tests`: `21 unit + 33 MySQL integration passed`
- `implementation_verification`: `passed`
- `dataset_scope`: `untouched`

## 实际命令与结果

1. `cd backend/business-service && mvn verify`
   - 结果：24 个单元测试和 38 个集成测试通过，0 failure，0 error。
   - 使用 Java 17 编译 81 个生产源文件。
   - MySQL 8.4 与 Apache Kafka 4.1.0 Testcontainers 均真实运行。
2. `python -m unittest discover -s contracts -t . -v`
   - 结果：35 个 Contract 测试通过，0 failure，0 error。
3. `docker compose -f infra/kafka/compose.yml config`
   - 结果：Compose 配置解析通过。
4. `docker compose -f infra/kafka/compose.yml up -d --wait`
   - 结果：Kafka healthy，Topic 初始化容器退出码为 0，Kafbat UI healthy。
5. `kafka-topics.sh --describe --topic factoryops.quality.incident.v1`
   - 结果：Topic 有 3 个 Partition，replication factor 为 1。
6. `Invoke-WebRequest http://localhost:8090/actuator/health`
   - 结果：Kafbat UI 返回 `{"status":"UP"}`。
7. `git diff --check`
   - 结果：通过。
8. Learning Gate 后重新执行 `cd backend/business-service && mvn verify`
   - 结果：27 个单元测试和 38 个集成测试通过，0 failure，0 error。
9. Learning Gate 后重新执行 `python -m unittest discover -s contracts -t . -v`
   - 结果：35 个 Contract 测试通过，0 failure，0 error。

## 关键证据

- Repository 只选择到期的 `PENDING` 事件，并按 `available_at, created_at, event_id` 稳定排序。
- Kafka Sender 原样发送已保存的 `message_key` 与 payload UTF-8 字节，不重新序列化 JSON。
- Producer 使用 `acks=all`、idempotence、5 秒 request timeout 和 10 秒 delivery timeout。
- 只有 Kafka acknowledgement 成功后才执行条件 `PENDING → PUBLISHED`；受影响行数不是 1 时明确失败。
- 不存在的 Topic 不会被隐式创建，发送会失败。
- `OutboxKafkaPublicationIT` 证明 Kafka 成功而数据库标记失败时，下一轮会发布相同 Key/Payload、不同 Offset 的重复消息，最终数据库才变为 `PUBLISHED`。

## 已知限制

- 本 Change 没有 Consumer；消息由未来的幂等 Consumer Change 消费。
- 当前只允许部署一个启用的 Publisher 实例，但这一点是部署约束，不是 Lease/Claim 代码保证。
- 当前没有 retry/backoff、`attempt_count` 更新、死信处理或多实例所有权协议。
- Kafbat UI 只用于本地学习，没有配置生产安全认证。

## Learning Gate

- 真实调用链 Walkthrough：完成。
- Owner 修改：完成 `last_successful_offset` 的状态传播、条件日志和日志断言。
- Failure/debug exercise：完成。
- 最终 diff review：完成并接受。
- 最终状态：`completed`，允许归档和合并 `main`。
