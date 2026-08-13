# Batch Lifecycle Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox syntax for tracking.

**Goal:** 建立可并发安全创建、查询、HOLD 和内部 RELEASE 的 Batch，并使 Inspection 具有不可变 Batch 归属。

**Architecture:** 在现有 Spring Boot 模块化单体中新建 batch domain/application/api/infrastructure 包；共享 READ COMMITTED TransactionTemplate。Flyway V3 建立 Batch、历史占位归属和证据外键；Application Service 通过条件更新及父行 `FOR UPDATE` 编排跨表不变量。

**Tech Stack:** Java 17、Spring Boot 4.1、JdbcTemplate、TransactionTemplate、Flyway、MySQL 8.4、Testcontainers、JUnit 5、MockMvc。

## Global Constraints

- Change ID 固定为 `2026-08-13-establish-batch-lifecycle`，学习等级 `deep`。
- 不提供 RELEASE HTTP API，不实现 Product/Order/Incident/Approval/Kafka/Outbox/Agent。
- 新 Inspection 必须提供真实 Batch；历史数据仅迁移到 `SYS-LEGACY-UNASSIGNED`。
- 所有关键生产行为先写失败测试并观察 RED；每个任务独立 commit。
- Docker/MySQL 全套验证未通过时不得进入 `review-handoff-ready`。
- 不读取、修改或提交 `dataset/`。

---

### Task 1: Batch Domain

**Files:**
- Create: `backend/business-service/src/main/java/com/factoryops/business/batch/domain/*.java`
- Test: `backend/business-service/src/test/java/com/factoryops/business/batch/domain/BatchTest.java`

**Interfaces:**
- Produces: `Batch.production(...)`, `Batch.restore(...)`, `HoldCommand`, `ReleaseCommand`, `BatchStatus`, `BatchKind`, `CommandDisposition`。

- [ ] 写格式、状态、原因、证据及重放/冲突失败测试并运行，确认因类型缺失而 RED。
- [ ] 实现最小不可变 Domain；时间使用传入 `Instant`，detail trim，标识符不规范化。
- [ ] 运行 `mvn -q -Dtest=BatchTest test`，确认 GREEN。
- [ ] 提交 `feat: add batch lifecycle domain`。

### Task 2: Flyway V3 and Persistence

**Files:**
- Create: `backend/business-service/src/main/resources/db/migration/V3__create_batches_and_assign_inspections.sql`
- Create: `backend/business-service/src/main/java/com/factoryops/business/batch/infrastructure/BatchJdbcRepository.java`
- Modify: Inspection persistence/domain for `batchId`
- Test: `backend/business-service/src/test/java/com/factoryops/business/batch/infrastructure/BatchMigrationIT.java`

**Interfaces:**
- Produces: `insert/find/findForUpdate/holdOpen/releaseHeld` 与 Inspection 的 Batch 归属读写。

- [ ] 写 V2→V3 历史回填、NOT NULL/FK/CHECK 和证据 FK 测试，确认 V3 缺失 RED。
- [ ] 实现 V3，顺序严格为占位 Batch、回填、NOT NULL、外键。
- [ ] 实现 repositories 及 hash+原文碰撞防御。
- [ ] 运行迁移/Repository IT，确认 GREEN。
- [ ] 提交 `feat: persist batches and inspection ownership`。

### Task 3: Batch Create and Query API

**Files:**
- Create: `backend/business-service/src/main/java/com/factoryops/business/batch/api/*.java`
- Create: `backend/business-service/src/main/java/com/factoryops/business/batch/application/BatchApplicationService.java`
- Test: `backend/business-service/src/test/java/com/factoryops/business/batch/api/BatchLifecycleHttpIT.java`

**Interfaces:**
- Produces: `POST /api/v1/batches`、`GET /api/v1/batches/{id}`、稳定错误映射。

- [ ] 写 201/200/409、422、404、占位查询和并发创建测试并确认 RED。
- [ ] 实现请求/响应、应用编排和异常映射；唯一键失败后在新读事务分类。
- [ ] 运行 Batch HTTP IT，确认 GREEN。
- [ ] 提交 `feat: create and query batches`。

### Task 4: Inspection Batch Ownership

**Files:**
- Modify: Inspection create request/response/domain/application/repository and existing ITs

**Interfaces:**
- Consumes: `BatchJdbcRepository.findForUpdate`。
- Produces: 必填 `batch_id`、四项身份 replay、OPEN/HELD 接收与 RELEASED/占位拒绝。

- [ ] 先修改测试：缺失/不存在 Batch、OPEN/HELD、RELEASED/占位、释放后 replay，并确认 RED。
- [ ] 实现已有 Inspection 快速分类；全新创建在写事务锁父 Batch并再次检查唯一身份。
- [ ] 运行 Inspection HTTP/Result 回归，确认 GREEN。
- [ ] 提交 `feat: bind inspections to batches`。

### Task 5: HOLD Evidence and Concurrency

**Files:**
- Modify: Batch API/Application/Repository
- Modify: Result Repository，提供精确证据读取
- Test: Batch HTTP IT

**Interfaces:**
- Produces: `POST /api/v1/batches/{id}/hold`，证据验证、applied/replayed/conflict。

- [ ] 写人工/过程 HOLD、异常证据、负向证据、相同/不同并发命令测试并确认 RED。
- [ ] 实现 Batch-first 锁顺序、不可变证据读取、关系验证与 `status='OPEN'` 条件更新。
- [ ] 注入写失败验证事务回滚，无部分 HOLD。
- [ ] 运行 Batch/Inspection/Result IT，确认 GREEN。
- [ ] 提交 `feat: hold batches with immutable evidence`。

### Task 6: Internal RELEASE and Race

**Files:**
- Modify: Batch Application/Repository
- Test: `backend/business-service/src/test/java/com/factoryops/business/batch/application/BatchReleaseIT.java`

**Interfaces:**
- Produces: 内部 `release(id, ReleaseCommand)`；不产生 HTTP route。

- [ ] 写 HELD→RELEASED、replay/conflict、OPEN 拒绝、无 HTTP route、Inspection/Release 竞争测试并确认 RED。
- [ ] 实现内部条件 RELEASE，与 Inspection 创建共享父行锁顺序。
- [ ] 运行相关 IT，确认 GREEN。
- [ ] 提交 `feat: add protected internal batch release`。

### Task 7: Verification and Handoff

**Files:**
- Modify: Change `tasks.md`、`verification.md`、`review-handoff.md`、`proposal.md`

- [ ] 运行 `mvn -q verify`，读取 XML 报告，确认 0 failure/error。
- [ ] 运行 Python Vision Contract 17 项回归、`git diff --check`、OpenSpec/placeholder/dataset scope 检查。
- [ ] 记录真实文件、符号、成功/失败调用链、owner `inspection_count` 任务和 HOLD 条件 SQL 故障实验。
- [ ] 提交文档、推送 feature branch，状态停在 `review-handoff-ready`，不合并 main。
