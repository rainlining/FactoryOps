# Accept Vision Inspection Result Implementation Plan

> **执行方式：** 当前实现会话使用测试先行与连续内部 commits；仅在范围扩张、设计歧义或需要环境安装授权时暂停。

**Goal:** 建立 Java/MySQL Vision Inspection Result Intake，支持严格 Contract、不可变持久化、HTTP/数据库幂等和并发冲突保护。

**Architecture:** 单个 Spring Boot 模块化单体中的 Inspection 模块。API Adapter 解析/校验 JSON，Domain 创建不可变结果，Application Service 用显式 TransactionTemplate 编排，JdbcTemplate Repository 与 MySQL 交互。

**Tech Stack:** Java 17、Maven、Spring Boot 4.1.0、Jackson 3、NetworkNT 3.0.6、Spring JDBC、Flyway、MySQL 8.4、Testcontainers/JUnit 5。

## Global Constraints

- 不修改 Vision Contract 1.0 Schema 语义。
- 不实现 Kafka/Outbox/Redis/Agent/Inspection 生命周期。
- 不修改 `dataset/`。
- 所有持久化测试使用真实 MySQL Testcontainer，不使用 H2。
- 运行时代码不依赖测试 hook；并发通过真实线程和数据库约束验证。

---

### Task 1: Java Build Baseline

**Files:**
- Create: `backend/business-service/pom.xml`
- Create: `backend/business-service/src/main/java/com/factoryops/business/FactoryOpsBusinessApplication.java`
- Create: `backend/business-service/src/main/resources/application.yml`
- Create: `backend/business-service/src/test/java/com/factoryops/business/ArchitectureSmokeTest.java`

**Steps:**
- [ ] 写启动上下文测试；先确认项目不存在而失败。
- [ ] 建立 Maven/Spring Boot 4.1.0、Java 17、Web/JDBC/Flyway/MySQL/Testcontainers/NetworkNT 依赖。
- [ ] Maven resources 将仓库根 `contracts/vision_inspection/v1.0/schema.json` 打入 classpath，不复制 Schema 源文件。
- [ ] 运行 smoke test 和 dependency tree，形成 baseline commit。

### Task 2: Contract Validation and Domain

**Files:**
- Create: `inspection/domain/InspectionResult.java`
- Create: `inspection/domain/InspectionResultIds.java`
- Create: `inspection/domain/InconsistentAnomalyDecisionException.java`
- Create: `inspection/application/VisionContractIssue.java`
- Create: `inspection/application/VisionContractException.java`
- Create: `inspection/application/VisionInspectionContractValidator.java`
- Create: `inspection/application/CanonicalJson.java`
- Test: matching `src/test/java/...` unit and shared-fixture tests.

**Interfaces:**
- `ValidatedVisionResult validate(JsonNode payload)` returns domain + canonical JSON + hashes.
- `CanonicalJson.canonicalize(JsonNode)` returns UTF-8 canonical bytes.
- Domain uses BigDecimal and rejects boolean/threshold inconsistency.

**Steps:**
- [ ] 先写 valid fixture、unsupported version、unknown field、score range 和 contradiction tests，观察缺少 API 的 RED。
- [ ] 实现固定 version→schema→domain 顺序和稳定第一 issue。
- [ ] 先写 key order、decimal tail zero、negative zero、exponent、array order canonical tests。
- [ ] 实现 recursive canonical writer 与 SHA-256。
- [ ] 运行 Task 2 tests，形成 domain/contract commit。

### Task 3: HTTP Contract

**Files:**
- Create: `inspection/api/InspectionResultController.java`
- Create: `inspection/api/InspectionResultResponse.java`
- Create: `inspection/api/ApiErrorResponse.java`
- Create: `inspection/api/InspectionExceptionHandler.java`
- Create: `inspection/application/InspectionResultIntake.java`
- Create: `inspection/application/IntakeDisposition.java`
- Test: `InspectionResultControllerTest.java`

**Interfaces:**
- `POST /api/v1/inspection-results` accepts raw JsonNode.
- `InspectionResultIntake.accept(JsonNode)` returns CREATED or REPLAYED.
- Exceptions map malformed JSON→400, Contract→422, identity conflict→409.

**Steps:**
- [ ] 先写 201/200/400/422/409 MockMvc tests。
- [ ] 实现最小 Controller/response/error mapping，以 in-memory fake intake 驱动 web tests。
- [ ] 检查错误只包含固定第一 issue，形成 API commit。

### Task 4: MySQL Schema and Repository

**Files:**
- Create: `src/main/resources/db/migration/V1__create_vision_inspection_results.sql`
- Create: `inspection/infrastructure/InspectionResultJdbcRepository.java`
- Create: `inspection/infrastructure/StoredInspectionResult.java`
- Test: `InspectionResultJdbcRepositoryIT.java`

**Schema:**
- 原始 ID/provenance 为 TEXT；ID SHA-256 为 BINARY(32)。
- `result_id_hash` UNIQUE，`inspection_id_hash` INDEX。
- decimal 规范化文本、canonical JSON、payload BINARY(32)、timestamps。
- 无 update method。

**Steps:**
- [ ] 先写 Testcontainers migration/repository tests，观察表不存在 RED。
- [ ] 添加 Flyway migration 和 JdbcTemplate row mapping/insert/find。
- [ ] 验证同 inspection 多 result、duplicate unique、完整 JSON/decimal roundtrip。
- [ ] 形成 persistence commit。

### Task 5: Explicit Transactions and Idempotency

**Files:**
- Create: `inspection/infrastructure/InspectionTransactionConfiguration.java`
- Create: `inspection/application/InspectionResultIntakeService.java`
- Create: `inspection/application/ResultIdentityConflictException.java`
- Test: `InspectionResultIntakeServiceIT.java`

**Steps:**
- [ ] 先写 created/replayed/conflict tests。
- [ ] 实现 READ COMMITTED read/write TransactionTemplate。
- [ ] 在 write transaction 外捕获 DuplicateKeyException，再用新 read transaction 查询赢家。
- [ ] 比较 result ID 原文防御 hash collision；比较 payload hash 决定 replay/conflict。
- [ ] 形成 transaction commit。

### Task 6: Full HTTP and Concurrency Integration

**Files:**
- Test: `InspectionResultHttpIT.java`
- Test: `InspectionResultConcurrencyIT.java`

**Steps:**
- [ ] 使用共享 valid/invalid fixtures 走真实 Controller→MySQL。
- [ ] 用 barrier 同时发起 identical requests，断言一行、created+replayed。
- [ ] 同时发起 conflicting requests，断言一行、created+409，赢家内容未覆盖。
- [ ] 重复运行并发测试以排除偶然串行通过。
- [ ] 运行全套 Maven tests、Flyway、compile、diff/scope checks。

### Task 7: Verification and Review Handoff

**Files:**
- Modify: Change `tasks.md`, `verification.md`, `proposal.md`
- Create: Change `review-handoff.md`

**Steps:**
- [ ] 写入实际命令、test count、Docker/MySQL 版本与限制。
- [ ] 记录真实文件/符号、成功/失败调用链、owner task 和 transaction failure exercise。
- [ ] 提交并推送 feature branch。
- [ ] 状态更新为 `review-handoff-ready`，实现会话停止，不归档、不合并 main。
