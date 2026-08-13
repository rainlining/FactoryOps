# Quality Incident Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 将合法异常 Vision Result、Inspection Completion 与唯一 OPEN Quality Incident 作为一个原子事务事实提交，并提供单体查询。

**Architecture:** `InspectionResultIntake` 保留最外层写事务并显式调用 `QualityIncidentService`；Incident Domain 负责身份与状态不变量，Repository 负责 V4 表，Query Service 负责只读查询。V4 使用相同派生算法回填历史异常 Result。

**Tech Stack:** Java 17、Spring Boot、JdbcTemplate、TransactionTemplate、MySQL 8.4、Flyway、JUnit 5、MockMvc、Testcontainers。

## Global Constraints

- 只实现 `2026-08-13-establish-quality-incident` 已批准范围。
- Java 代码必须采用正常换行和统一格式；禁止压缩成单行。
- 每个行为先写失败测试并观察预期失败，再写最小实现。
- 不修改 `dataset/`，不实现 Kafka、Outbox、Agent、自动 HOLD 或 Incident 状态迁移。
- Incident ID 固定为 `QI-` + 大写完整 SHA-256，输入命名空间为 `factoryops:quality-incident:v1:result:`。

---

### Task 1: Incident Domain 与派生身份

**Files:**
- Create: `backend/business-service/src/main/java/com/factoryops/business/incident/domain/QualityIncident.java`
- Create: `backend/business-service/src/main/java/com/factoryops/business/incident/domain/QualityIncidentId.java`
- Test: `backend/business-service/src/test/java/com/factoryops/business/incident/domain/QualityIncidentTest.java`

**Interfaces:**
- Produces: `QualityIncident.open(batchId, inspectionId, resultId, createdAt)`；`QualityIncidentId.fromResultId(resultId)`。

- [ ] 写派生稳定性、不同 Result、OPEN/1.0 和必填证据失败测试。
- [ ] 运行 `mvn -Dtest=QualityIncidentTest test`，确认因类型缺失失败。
- [ ] 实现最小 Domain 与派生算法。
- [ ] 重跑测试并提交 `feat: add quality incident domain`。

### Task 2: V4 Schema、回填与 Repository

**Files:**
- Create: `backend/business-service/src/main/resources/db/migration/V4__create_quality_incidents.sql`
- Create: `backend/business-service/src/main/java/com/factoryops/business/incident/infrastructure/QualityIncidentJdbcRepository.java`
- Create: `backend/business-service/src/test/java/com/factoryops/business/incident/infrastructure/QualityIncidentMigrationIT.java`

**Interfaces:**
- Consumes: `QualityIncident`。
- Produces: `insert`、`findById`、`findByResultId`。

- [ ] 写 V1→V4 回填测试：异常回填、正常跳过、时间继承、唯一/CHECK/证据约束。
- [ ] 运行迁移测试，确认缺少 V4 失败。
- [ ] 实现 V4 和 Repository 映射。
- [ ] 重跑迁移测试并提交 `feat: persist quality incidents`。

### Task 3: 三对象原子事务与 Intake 响应

**Files:**
- Create: `backend/business-service/src/main/java/com/factoryops/business/incident/application/QualityIncidentService.java`
- Modify: `backend/business-service/src/main/java/com/factoryops/business/inspection/application/InspectionResultIntake.java`
- Modify: Result Intake HTTP response/controller files。
- Modify/Test: `backend/business-service/src/test/java/com/factoryops/business/inspection/api/InspectionResultHttpIT.java`

**Interfaces:**
- Produces: `QualityIncidentService.openOrFind(Inspection, InspectionResult)` 返回可空 Incident ID。
- Result Intake outcome 增加可空 `incidentId`。

- [ ] 写异常/正常、replay、conflict、三种 origin、Batch 不变和并发响应测试。
- [ ] 运行目标 IT，确认缺少 `incident_id` 或 Incident 行失败。
- [ ] 在现有 TransactionTemplate 内接入 Service，保持显式同步调用。
- [ ] 写 Incident INSERT 故障测试，断言 Result=0、Incident=0、Inspection=PENDING。
- [ ] 观察失败后实现/修正异常传播，重跑目标 IT 并提交 `feat: open incidents atomically with anomaly results`。

### Task 4: Incident 单体查询 API

**Files:**
- Create: `backend/business-service/src/main/java/com/factoryops/business/incident/application/QualityIncidentQueryService.java`
- Create: `backend/business-service/src/main/java/com/factoryops/business/incident/api/QualityIncidentController.java`
- Create: response、not-found exception 与 handler。
- Test: `backend/business-service/src/test/java/com/factoryops/business/incident/api/QualityIncidentHttpIT.java`

**Interfaces:**
- Produces: `GET /api/v1/quality-incidents/{incident_id}` 和稳定 404。

- [ ] 写查询快照与 `quality_incident_not_found` 测试。
- [ ] 运行目标 IT，确认路由不存在失败。
- [ ] 实现只读 Service、Controller、Response 和错误映射。
- [ ] 重跑并提交 `feat: query quality incidents`。

### Task 5: 完整验证、格式门禁与 Handoff

**Files:**
- Modify: 当前 Change 的 `tasks.md`、`verification.md`、`review-handoff.md`、`proposal.md`。

- [ ] 对本 Change 涉及的 Java 文件运行 google-java-format。
- [ ] 扫描 Java 超长行，确认没有压缩类、方法、import 或测试语句。
- [ ] 运行 `mvn verify`、Python Vision Contract、`git diff --check` 和 dataset scope 检查。
- [ ] 填写真实调用链、验证证据、owner 修改与 failure exercise。
- [ ] 提交、推送分支，并停在 `review-handoff-ready`。
