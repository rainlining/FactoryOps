# 技术设计：Outbox 可靠发布到 Kafka

## 1. 要解决的问题

MySQL 已保存不可变 PENDING Outbox，但数据库提交本身不会把事件送入 Kafka。本 Change 需要在不重新引入业务事务与 Kafka 双写的前提下，可靠地把已有事实发布到 Business World 与 Agent World 之间的 Kafka Backbone。

可靠在这里表示“不静默丢失”：Kafka 未确认时不能标记 PUBLISHED；Kafka 已确认但 MySQL 更新失败时允许再次发送稳定的 `event_id`。它不表示跨 MySQL 与 Kafka exactly-once。

## 2. 组件边界

Publisher 位于现有 Java Business Service 的独立 `outbox.publisher` 模块：

```text
MySQL outbox_events
        ↓ 查询 PENDING
Outbox Poller
        ↓ 逐条交付
Kafka Event Sender
        ↓ 原始 UTF-8 bytes
Kafka Broker
        ↓ acknowledgement
Outbox Publication Service
        ↓ 条件更新
MySQL PUBLISHED
```

- Poller：固定延迟调度、批量读取、轮次摘要。
- Publication Service：逐事件编排、失败隔离，不持有跨网络数据库事务。
- Kafka Event Sender：发送 topic/key/value，等待 ack，返回 partition/offset；不访问数据库。
- Repository：稳定查询 PENDING 和条件更新 PUBLISHED。
- Kafbat UI：仅用于本地观察和手工学习，不被生产代码或自动化测试依赖。

## 3. 单实例约束

`factoryops.outbox.publisher.enabled` 默认 `false`。Docker 学习配置只启用一个 Publisher。由于本 Change不实现 lease 或锁，代码无法可靠探测另一台机器上的实例；这是明确的部署不变量，而不是自动保证。

多实例 claiming、owner、lease expiry、安全释放和 `SKIP LOCKED` 必须由后续独立 Deep Change 解决。

## 4. 数据流与事务

每轮查询最多 `batch-size` 条 `PENDING AND available_at <= CURRENT_TIMESTAMP(6)`，按 `available_at, created_at, event_id` 排序。对每条记录：

1. 读取已保存 topic、message key 和 payload。
2. payload 原文编码为 UTF-8，不解析重写。
3. 发送 Kafka 并同步等待 acknowledgement，受 delivery timeout 限制。
4. ack 成功后开启短 MySQL 事务。
5. 条件执行 PENDING → PUBLISHED，并设置数据库 `CURRENT_TIMESTAMP(6)`。
6. 要求更新一行并提交。

Kafka 网络调用不处于 MySQL 事务内。查询可成批，但 publish/ack/status update 逐事件完成。

## 5. Kafka 配置与路由

- `acks=all`
- `enable.idempotence=true`
- Broker `auto.create.topics.enable=false`
- 明确 `delivery.timeout.ms`
- topic：Outbox 保存的 `factoryops.quality.incident.v1`
- key：Outbox 保存的 Incident ID
- value：Outbox payload UTF-8 bytes
- 不新增 headers

本地 Topic 由初始化任务创建为 3 partitions、1 replica。3 partitions 用于观察 key→partition 映射；单副本只适用于本地学习，不能证明生产高可用。

## 6. 失败路径

### MySQL 查询失败

当前轮结束，等待下一次 fixed delay，不使用旧结果。

### Kafka 发送失败或超时

事件保持 PENDING，记录分类错误，继续后续事件。下一轮再次尝试。

### Kafka 已确认、MySQL 更新失败

Kafka 已有消息而数据库可能仍为 PENDING。下一轮会再次发送相同 event ID。这是必须展示的 at-least-once 重复窗口。

### 条件更新影响 0 行

视为状态完整性或非法并发错误，不做无条件覆盖。下一轮重新读取实际状态。

### 永久坏事件

本 Change 不更新 attempt count、available_at 或 last error；永久错误会反复尝试并由日志暴露。异常分类、backoff、FAILED 和人工恢复属于后续可靠性 Change。

## 7. 调度与关闭

- `fixed delay` 从上一轮完成后开始计时。
- 默认 poll delay 1 秒、batch size 50、delivery timeout 10 秒。
- 正常 shutdown 后不启动新轮次；正在等待的单条发送由 delivery timeout 约束。
- 强制终止最多造成重复，不得造成“未发送却 PUBLISHED”。

## 8. 可观测性

逐事件结构化日志包含 event ID、topic、key、partition、offset、ack latency、状态结果和失败分类，不输出完整 payload。每轮输出 selected、published、failed、duration。

Prometheus、告警和 Consumer Lag 不在本 Change。手工证据由 Kafbat UI、MySQL 查询和 Java 日志共同提供。

## 9. 测试策略

- 单元测试：ack 顺序、失败不更新、继续后续事件、影响 0 行、disabled、UTF-8 原始 bytes。
- MySQL 集成：到期过滤、稳定排序、batch size、条件更新和数据库 published time。
- Kafka Testcontainers：真实 broker、显式 Topic、key/value bytes、partition/offset 和最终 PUBLISHED。
- 故障测试：Kafka 不可达、Topic 缺失、Kafka 成功但数据库更新失败，以及再次发布后的相同 event ID/不同 offset。

自动化 Testcontainers 生命周期短；Docker Compose + Kafbat UI Learning Lab 用于持续观察和操作。

## 10. 放弃的方案

- 独立 Publisher 微服务：当前部署成本过高。
- Debezium CDC：绕过本轮 Producer/ack 学习目标。
- 多实例 Lease：独立并发问题，当前范围过大。
- MySQL 事务内等待 Kafka：形成长事务且不能获得跨系统原子性。
- Kafka Transaction：不能与 MySQL 事务组成原子提交。
- 批量异步发送后统一更新：失败归属复杂。
- 自动创建 Topic：掩盖配置错误。
- 全 Mock Kafka：无法证明真实 partition、offset 和网络行为。
- 同时实现 Consumer：会混入 offset、幂等登记和 Agent Runtime 边界。
