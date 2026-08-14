# Outbox Kafka Publication 规格增量

## 新增需求

### Requirement: Publisher 必须默认关闭并以单实例运行

Outbox Publisher 必须通过显式配置启用，默认关闭。在并发领取能力完成前，同一数据库只能连接一个启用 Publisher 的应用实例；系统不得声称已自动阻止多实例。

### Requirement: Publisher 必须稳定选择到期事件

每轮必须只选择 `status='PENDING'` 且 `available_at` 不晚于数据库当前时间的事件，按 `available_at, created_at, event_id` 排序，并受可配置 batch size 限制。固定延迟必须从上一轮结束后计算，单实例内不得重叠执行两轮。

### Requirement: Kafka Record 必须来自不可变 Outbox

Producer 必须使用 Outbox 保存的 topic 和 message key，并把已保存 payload 原文直接编码为 UTF-8 value。发布路径不得查询当前业务状态重建事件，不得重新序列化 JSON，也不得自行增加未版本化 Kafka headers。

### Requirement: Topic 必须显式存在

Kafka Broker 必须禁用自动创建 Topic。`factoryops.quality.incident.v1` 必须由基础设施显式创建；本地学习环境使用 3 partitions 和 1 replica。Topic 不存在时发送必须失败且 Outbox 保持 PENDING。

### Requirement: Broker acknowledgement 成功后才能标记 PUBLISHED

Producer 必须使用 `acks=all`、启用 Producer idempotence，并受明确 delivery timeout 限制。只有收到 broker acknowledgement 后，系统才能在独立短 MySQL 事务中更新 PUBLISHED。

### Requirement: PUBLISHED 更新必须防止陈旧覆盖

状态更新必须包含 `WHERE event_id=? AND status='PENDING'`，设置 `published_at` 为数据库当前时间，并要求影响行数恰好为 1。影响 0 行必须报告状态完整性或非法并发错误，不得无条件覆盖。

### Requirement: 单条失败不得阻塞无关事件

查询失败必须结束当前轮；单条 Kafka 发送失败、超时或状态更新失败必须记录后继续当前批次的后续事件。失败事件不得被错误标记 PUBLISHED。

### Requirement: 系统必须明确保留 at-least-once 重复窗口

Kafka 已确认而 MySQL 状态更新尚未成功时，进程崩溃或数据库错误可以使下一轮再次发布相同 `event_id`。重复记录必须保持相同 key 和 payload，但具有不同 offset。系统不得把 Producer idempotence 表述为跨重启 exactly-once。

### Requirement: 发布行为必须可观察

逐事件日志必须包含 event ID、topic、message key、成功时的 partition/offset、ack 耗时、状态更新结果与失败分类，但不得记录完整 payload。每轮必须记录 selected、published、failed 和 duration 摘要。

### Requirement: 本地环境必须支持可视化学习

Docker 学习环境必须提供单节点 KRaft Kafka、显式 Topic 初始化和 Kafbat UI。Learning Lab 必须指导观察 topic、partition、offset、key、payload、PENDING/PUBLISHED 状态以及 at-least-once 重复。
