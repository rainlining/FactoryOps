# 学习计划：2026-08-14-publish-outbox-events-to-kafka

## 元数据

- `learning_level`: `deep`
- `gate_status`: `preflight-passed`

## 编码前必须理解

- Producer、Broker、Topic、Partition、Offset 和 acknowledgement 的关系。
- `acks=all` 与 Producer idempotence 解决什么、不解决什么。
- 为什么 Kafka 成功后才能写 PUBLISHED。
- 为什么 Kafka 成功、MySQL 更新失败会产生 at-least-once 重复。
- 为什么 Kafka 网络调用不能包在 MySQL 长事务中。
- 单实例部署约束与未来多实例 Lease 的边界。
- Testcontainers 自动化环境与 Kafbat UI 持续学习环境的区别。

## Code Walkthrough 路线

Review 会话必须沿真实文件覆盖：Poller → PENDING Repository → Publication Service → Kafka Sender → broker ack metadata → PUBLISHED Repository → 成功/失败日志 → Testcontainers 与 Learning Lab。

## 项目所有者亲自修改任务

在每轮 Publisher 摘要日志中增加 `last_successful_offset`。只有本轮至少成功发布一条事件时才出现；不得写入 Outbox 表或事件 payload。最终以日志断言测试验收。

## Failure/Debug Exercise

- 注入故障：让 Kafka 已成功接收，但 PUBLISHED 条件更新失败。
- 预期：Kafka 已有消息，MySQL 仍为 PENDING。
- 恢复：复位更新逻辑并再次运行 Publisher。
- 观察：Kafbat UI 中出现相同 event ID 和相同 key/payload，但 offset 不同；MySQL 最终为 PUBLISHED。
- 常见错误：第一次更新失败却被吞掉并误报成功，或第二次发布重建了不同 payload。
- 完成后应能解释：重复窗口位于哪两步之间，为什么 Producer idempotence 不能跨进程重启消除它。

## Learning Gate

- [ ] 能解释 Kafka 核心对象和本 Change 的 ack 语义。
- [ ] 能沿成功调用链定位查询、发送、ack 和状态更新。
- [ ] 能在 Kafbat UI 中找到 topic、key、partition、offset 和 payload。
- [ ] 能定位并解释至少一条发送失败路径和重复窗口。
- [ ] 能指出单实例约束实际在哪里配置、哪里没有被代码保证。
- [ ] 完成 owner 修改任务。
- [ ] 完成 failure/debug exercise 并依据 Kafka/MySQL/日志证据判断。
- [ ] review 最终 diff 并明确接受。
