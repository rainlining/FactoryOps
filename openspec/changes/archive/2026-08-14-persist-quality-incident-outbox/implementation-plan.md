# Transactional Outbox 持久化实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 新建 Quality Incident 时，在同一个 MySQL 事务中保存唯一、不可变、符合 v1.0 Contract 的 PENDING Outbox。

**Architecture:** `QualityIncidentOpenedEventFactory` 纯函数生成事件，`OutboxEventJdbcRepository` 负责持久化，`QualityIncidentService` 维护 Incident/Outbox 成对不变量；现有 `InspectionResultIntakeService` 继续拥有最外层事务。

**Tech Stack:** Java 17、Spring Boot JDBC、Flyway、MySQL 8.4、Jackson、NetworkNT JSON Schema、JUnit 5、Testcontainers。

## Global Constraints

- 不实现 Kafka Producer、Consumer、领取锁、retry 或 FAILED 状态。
- Java 文件必须正常格式化，不得压缩为单行。
- 所有行为先写失败测试，再写最小实现。
- 不修改或提交 `dataset/`。

---

### Task 1：Event Factory 与 Contract Test

**Files:**
- Create: `backend/business-service/src/main/java/com/factoryops/business/outbox/domain/OutboxEvent.java`
- Create: `backend/business-service/src/main/java/com/factoryops/business/outbox/application/QualityIncidentOpenedEventFactory.java`
- Create: `backend/business-service/src/test/java/com/factoryops/business/outbox/application/QualityIncidentOpenedEventFactoryTest.java`
- Modify: `backend/business-service/pom.xml`

**Interfaces:**
- Consumes: `QualityIncident`。
- Produces: `OutboxEvent create(QualityIncident incident, Instant outboxCreatedAt)`。

- [ ] 写失败测试，断言稳定 event ID、路由、业务/技术时间、PENDING 初始状态和 canonical payload。
- [ ] 运行目标测试，确认因类型缺失而失败。
- [ ] 实现不可变 `OutboxEvent` 与 Event Factory。
- [ ] 用冻结 Schema 验证 Java 真实 payload，并确认测试转绿。
- [ ] 提交 Event Factory 边界。

### Task 2：V5 Outbox Schema 与历史回填

**Files:**
- Create: `backend/business-service/src/main/resources/db/migration/V5__create_and_backfill_outbox_events.sql`
- Create: `backend/business-service/src/test/java/com/factoryops/business/outbox/infrastructure/OutboxMigrationIT.java`

**Interfaces:**
- Produces: `outbox_events` 表、约束、索引以及历史 OPEN Incident 的 PENDING 行。

- [ ] 写 V4→V5 失败迁移测试，断言回填数量、occurred_at、状态、event ID 与 canonical payload。
- [ ] 运行目标集成测试，确认因 V5 缺失而失败。
- [ ] 创建表、外键、唯一键、CHECK、索引和回填 SQL。
- [ ] 验证回填 payload 通过冻结 Contract，测试转绿。
- [ ] 提交数据库边界。

### Task 3：Repository 与内容核对

**Files:**
- Create: `backend/business-service/src/main/java/com/factoryops/business/outbox/infrastructure/OutboxEventJdbcRepository.java`
- Create: `backend/business-service/src/main/java/com/factoryops/business/outbox/application/OutboxIntegrityException.java`
- Create: `backend/business-service/src/test/java/com/factoryops/business/outbox/infrastructure/OutboxEventJdbcRepositoryIT.java`

**Interfaces:**
- Produces: `insert(OutboxEvent)`、`findByEventId(String)`、`requireMatching(OutboxEvent)`。

- [ ] 写失败测试覆盖精确保存/读取、两个唯一键、外键、JSON_VALID 和冲突核对。
- [ ] 运行目标测试并确认缺失实现失败。
- [ ] 实现 JDBC Repository 与明确完整性异常。
- [ ] 运行测试并转绿。
- [ ] 提交持久化边界。

### Task 4：接入现有事务与 replay

**Files:**
- Modify: `backend/business-service/src/main/java/com/factoryops/business/incident/application/QualityIncidentService.java`
- Modify: `backend/business-service/src/test/java/com/factoryops/business/inspection/api/InspectionResultHttpIT.java`

**Interfaces:**
- 新 Incident：Incident INSERT 后 Event Factory + Outbox INSERT。
- Replay：已有 Incident 必须存在完全匹配的 Outbox。

- [ ] 写失败 HTTP/MySQL 测试覆盖新建一个 Outbox、正常结果零 Outbox、顺序 replay 不增加、并发 replay 只有一个。
- [ ] 运行集成测试确认缺失 Outbox 断言失败。
- [ ] 注入 Factory/Repository 并在现有事务中成对创建、在 replay 中核对。
- [ ] 写缺失/冲突 Outbox 负向测试并转绿。
- [ ] 提交事务编排边界。

### Task 5：原子回滚与完整验证

**Files:**
- Modify: `backend/business-service/src/test/java/com/factoryops/business/inspection/api/InspectionResultHttpIT.java`
- Modify: 当前 Change 的 `tasks.md`、`verification.md`、`review-handoff.md`。

**Interfaces:**
- 证据：Outbox CHECK 失败后 Inspection=PENDING 且 Result/Incident/Outbox 均为 0。

- [ ] 写并运行故障注入测试，确认没有事务接入时测试失败。
- [ ] 使原子回滚测试通过，并运行 `mvn verify` 与全部 Python Contract 测试。
- [ ] 格式化 Java，运行 `git diff --check` 并检查 dataset scope。
- [ ] 填写 handoff、提交、推送并停在 `review-handoff-ready`。
