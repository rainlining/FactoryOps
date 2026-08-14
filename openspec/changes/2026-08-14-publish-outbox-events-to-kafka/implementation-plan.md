# Outbox Kafka Publisher Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 将 PENDING Quality Incident Outbox 以单实例、at-least-once 语义发布到真实 Kafka，并在 broker acknowledgement 后条件更新为 PUBLISHED。

**Architecture:** 现有 Business Service 内新增独立 Publisher 模块。Repository 批量读取但 Publication Service 逐条调用 `OutboxEventSender`；Kafka sender 返回 partition/offset/ack latency 后，Repository 在短事务中执行 PENDING→PUBLISHED。Docker Compose 提供 KRaft Kafka、Topic 初始化和 Kafbat UI，Testcontainers 提供自动化传输验证。

**Tech Stack:** Java 17、Spring Boot 4.1、Spring JDBC、Spring Kafka、MySQL 8.4、Apache Kafka KRaft、Testcontainers、JUnit 6、AssertJ、Docker Compose、Kafbat UI。

## Global Constraints

- Publisher 默认关闭；同一数据库只能连接一个启用实例。
- 不实现 Consumer、Lease、锁、backoff、FAILED、dead-letter、Prometheus 或 exactly-once。
- Kafka 网络调用期间不得持有 MySQL 事务。
- value 必须是 Outbox payload 原文的 UTF-8 bytes，不得重新序列化。
- `acks=all`、`enable.idempotence=true`、`allow.auto.create.topics=false`。
- 只有 broker acknowledgement 成功后才允许条件更新 PUBLISHED。
- `dataset/` 不得修改或提交。

---

### Task 1: 冻结 Publication Service 的逐事件编排

**Files:**
- Create: `backend/business-service/src/main/java/com/factoryops/business/outbox/publisher/OutboxEventSender.java`
- Create: `backend/business-service/src/main/java/com/factoryops/business/outbox/publisher/KafkaPublication.java`
- Create: `backend/business-service/src/main/java/com/factoryops/business/outbox/publisher/PublicationRoundSummary.java`
- Create: `backend/business-service/src/main/java/com/factoryops/business/outbox/publisher/OutboxPublicationService.java`
- Test: `backend/business-service/src/test/java/com/factoryops/business/outbox/publisher/OutboxPublicationServiceTest.java`

**Interfaces:**
- `OutboxEventSender.send(OutboxEvent event) -> KafkaPublication`
- `KafkaPublication(int partition, long offset, Duration acknowledgementLatency)`
- `OutboxPublicationService.publish(List<OutboxEvent> events) -> PublicationRoundSummary`
- Service 依赖 sender 与一个只暴露 `markPublished(eventId)` 的 Repository 边界。

- [ ] **Step 1: 写失败测试**

用手写 recording sender/repository 验证：成功顺序为 send→mark；第一条 sender 抛异常时不 mark 且第二条继续；mark 抛异常时下一条继续；摘要 selected/published/failed 正确。

- [ ] **Step 2: 验证 RED**

Run: `mvn -Dtest=OutboxPublicationServiceTest test`
Expected: FAIL，因为 Publisher 类型尚不存在。

- [ ] **Step 3: 最小实现**

实现聚焦接口和同步逐事件循环。每个事件单独 try/catch，成功后才调用 `markPublished`，日志不输出 payload。

- [ ] **Step 4: 验证 GREEN**

Run: `mvn -Dtest=OutboxPublicationServiceTest test`
Expected: PASS。

- [ ] **Step 5: Commit**

`git commit -m "feat: orchestrate outbox publication acknowledgements"`

### Task 2: 实现稳定查询和条件状态更新

**Files:**
- Modify: `backend/business-service/src/main/java/com/factoryops/business/outbox/infrastructure/OutboxEventJdbcRepository.java`
- Test: `backend/business-service/src/test/java/com/factoryops/business/outbox/infrastructure/OutboxPublisherRepositoryIT.java`

**Interfaces:**
- `findPublishable(int limit) -> List<OutboxEvent>`
- `markPublished(String eventId) -> void`
- `markPublished` 以独立 `TransactionTemplate` 或事务代理运行；影响行数不是 1 时抛 `OutboxPublicationStateException`。

- [ ] **Step 1: 写 MySQL 失败测试**

插入 PENDING/PUBLISHED/未来 available_at 记录，断言只返回到期 PENDING、顺序为 available_at/created_at/event_id、limit 生效；断言一次 PENDING→PUBLISHED 成功并有数据库时间，第二次更新失败。

- [ ] **Step 2: 验证 RED**

Run: `mvn -Dit.test=OutboxPublisherRepositoryIT verify`
Expected: FAIL，因为查询与状态更新方法不存在。

- [ ] **Step 3: 最小 JDBC 实现**

查询使用 `status='PENDING' AND available_at<=CURRENT_TIMESTAMP(6)` 和固定 `ORDER BY`；limit 作为正整数绑定。更新使用 `WHERE event_id=? AND status='PENDING'` 与 `CURRENT_TIMESTAMP(6)`。

- [ ] **Step 4: 验证 GREEN**

Run: `mvn -Dit.test=OutboxPublisherRepositoryIT verify`
Expected: PASS。

- [ ] **Step 5: Commit**

`git commit -m "feat: select and publish pending outbox rows"`

### Task 3: 接入真实 Kafka Producer acknowledgement

**Files:**
- Modify: `backend/business-service/pom.xml`
- Create: `backend/business-service/src/main/java/com/factoryops/business/outbox/publisher/KafkaOutboxEventSender.java`
- Create: `backend/business-service/src/main/java/com/factoryops/business/outbox/publisher/OutboxPublisherConfiguration.java`
- Modify: `backend/business-service/src/main/resources/application.yml`
- Test: `backend/business-service/src/test/java/com/factoryops/business/outbox/publisher/KafkaOutboxEventSenderIT.java`

**Interfaces:**
- Sender 以 `ProducerRecord<String, byte[]>` 发送 `event.topic()`、`event.messageKey()` 和 `event.payload().getBytes(UTF_8)`。
- `KafkaTemplate.send(...).get(deliveryTimeout)` 成功后由 `RecordMetadata` 构建 `KafkaPublication`。

- [ ] **Step 1: 写真实 Kafka 失败测试**

Testcontainers 显式创建 3-partition Topic；调用 sender 后用原生 test consumer 读取，逐字节断言 key/value，断言 publication 的 partition/offset 与 record 一致。另测不存在 Topic 时 future 失败。

- [ ] **Step 2: 验证 RED**

Run: `mvn -Dit.test=KafkaOutboxEventSenderIT verify`
Expected: FAIL，因为依赖、配置和 sender 尚不存在。

- [ ] **Step 3: 添加依赖与最小实现**

加入 Spring Kafka 和 Testcontainers Kafka；Producer 配置固定 acks/all、idempotence true、auto-create false、delivery timeout；不添加 headers，不解析 payload。

- [ ] **Step 4: 验证 GREEN**

Run: `mvn -Dit.test=KafkaOutboxEventSenderIT verify`
Expected: PASS，并得到真实 partition/offset。

- [ ] **Step 5: Commit**

`git commit -m "feat: send immutable outbox records to kafka"`

### Task 4: 增加默认关闭的 fixed-delay Poller

**Files:**
- Create: `backend/business-service/src/main/java/com/factoryops/business/outbox/publisher/OutboxPublisherProperties.java`
- Create: `backend/business-service/src/main/java/com/factoryops/business/outbox/publisher/ScheduledOutboxPublisher.java`
- Modify: `backend/business-service/src/main/java/com/factoryops/business/outbox/publisher/OutboxPublisherConfiguration.java`
- Modify: `backend/business-service/src/main/resources/application.yml`
- Test: `backend/business-service/src/test/java/com/factoryops/business/outbox/publisher/ScheduledOutboxPublisherTest.java`

**Interfaces:**
- Properties：`enabled=false`、`pollDelay=1s`、`batchSize=50`、`deliveryTimeout=10s`。
- `runOnce()` 查询后调用 service，返回摘要以便测试；`@Scheduled(fixedDelayString=...)` 只在 enabled=true Bean 存在时运行。

- [ ] **Step 1: 写失败测试**

验证 `runOnce` 把配置 batch size 传给 Repository；没有事件时仍返回零摘要；配置关闭时 Spring Context 不创建 scheduled publisher；日志参数包含轮次计数但不包含 payload。

- [ ] **Step 2: 验证 RED**

Run: `mvn -Dtest=ScheduledOutboxPublisherTest test`
Expected: FAIL，因为 Poller 和 Properties 不存在。

- [ ] **Step 3: 最小实现**

使用 `@ConfigurationProperties`、`@ConditionalOnProperty` 和 fixed delay。启动时明确记录 enabled/disabled；默认测试上下文不运行后台任务。

- [ ] **Step 4: 验证 GREEN**

Run: `mvn -Dtest=ScheduledOutboxPublisherTest test`
Expected: PASS。

- [ ] **Step 5: Commit**

`git commit -m "feat: schedule single-instance outbox polling"`

### Task 5: 验证端到端发布与 at-least-once 窗口

**Files:**
- Create: `backend/business-service/src/test/java/com/factoryops/business/outbox/publisher/OutboxKafkaPublicationIT.java`

**Interfaces:**
- 复用真实 MySQL、Kafka、Repository、Publication Service 和 sender；测试显式调用 `runOnce`，不依赖时间等待 scheduler。

- [ ] **Step 1: 写端到端测试**

验证 PENDING→Kafka record→PUBLISHED；Kafka 不可达/Topic 缺失保持 PENDING；包装 Repository 让首次 `markPublished` 失败，断言 Kafka 已有一条而 MySQL PENDING，再运行后出现相同 key/value、不同 offset 且最终 PUBLISHED。

- [ ] **Step 2: 验证测试**

Run: `mvn -Dit.test=OutboxKafkaPublicationIT verify`
Expected: PASS；若暴露实现缺陷，按失败证据回到对应任务修复。

- [ ] **Step 3: Commit**

`git commit -m "test: prove outbox kafka at-least-once delivery"`

### Task 6: 建立 Kafka + Kafbat UI Learning Lab

**Files:**
- Create: `infra/kafka/compose.yml`
- Create: `infra/kafka/create-topics.sh`
- Create: `infra/kafka/README.md`
- Create: `infra/kafka/learning-lab.md`
- Create: `infra/kafka/.env.example`

**Interfaces:**
- Compose 提供 `kafka`、`kafka-init`、`kafbat-ui`；Kafka 同时公布容器内 listener 与 Windows host listener。
- `kafka-init` 幂等创建 `factoryops.quality.incident.v1`，3 partitions、replication factor 1。
- Kafbat UI 只连接内部 listener，映射一个明确本地端口。

- [ ] **Step 1: 写 Compose 配置验证**

Run: `docker compose -f infra/kafka/compose.yml config`
Expected: PASS，且三个服务和 listener 引用解析成功。

- [ ] **Step 2: 启动并验证基础设施**

Run: `docker compose -f infra/kafka/compose.yml up -d --wait`
Run: `docker compose -f infra/kafka/compose.yml exec kafka kafka-topics.sh --bootstrap-server kafka:9092 --describe --topic factoryops.quality.incident.v1`
Expected: 3 partitions、replication factor 1；Kafbat UI health 可访问。

- [ ] **Step 3: 编写中文 Learning Lab**

覆盖启动、UI 导航、产生 PENDING Outbox、启停 Kafka、观察 PUBLISHED、故障窗口、重复 event ID/不同 offset、MySQL 查询、Kafka CLI 和清理命令。

- [ ] **Step 4: Commit**

`git commit -m "docs: add kafka visualization learning lab"`

### Task 7: 完整验证与 Review Handoff

**Files:**
- Modify: `openspec/changes/2026-08-14-publish-outbox-events-to-kafka/tasks.md`
- Modify: `openspec/changes/2026-08-14-publish-outbox-events-to-kafka/verification.md`
- Modify: `openspec/changes/2026-08-14-publish-outbox-events-to-kafka/review-handoff.md`
- Modify: `openspec/changes/2026-08-14-publish-outbox-events-to-kafka/proposal.md`

- [ ] **Step 1: 格式化和全量验证**

Run: `mvn verify`
Run: `python -m unittest discover -s contracts -t . -v`
Run: `docker compose -f infra/kafka/compose.yml config`
Run: `git diff --check`
Expected: 全部 exit 0，并记录精确测试数量。

- [ ] **Step 2: 范围核对**

确认没有 Consumer、Lease/backoff/FAILED/Prometheus、Contract 改动或 `dataset/` 修改；检查 Publisher 默认关闭。

- [ ] **Step 3: 填写 Handoff**

记录 branch/worktree/base/head、真实符号与调用链、验证证据、已知单实例限制、Owner 修改和 Failure/Debug Exercise 恢复步骤；状态停在 `review-handoff-ready`。

- [ ] **Step 4: Commit**

`git commit -m "docs: hand off kafka publisher review"`

