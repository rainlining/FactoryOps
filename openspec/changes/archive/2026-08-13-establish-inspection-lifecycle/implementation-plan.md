# Inspection Lifecycle Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox syntax for tracking.

**Goal:** 创建和查询 Inspection，并在一个事务内保存匹配的 Vision Result 与执行首次完成状态迁移。

**Architecture:** 扩展现有 Spring Boot Inspection 模块。Domain 表达状态/输入不变量，Application Service 用显式 TransactionTemplate 编排，JdbcTemplate/Flyway/MySQL 提供持久化、条件更新、迁移与外键防线。

**Tech Stack:** Java 17、Spring Boot 4.1、JdbcTemplate、TransactionTemplate、Flyway、MySQL 8.4、Testcontainers、JUnit 5、MockMvc。

## Global Constraints

- 不修改 Vision Inspection Contract 1.0。
- 只支持 `PENDING → COMPLETED`；不实现取消、重开、Batch、Incident、Kafka、Outbox 或 Agent。
- Result 插入与 Inspection 完成必须处于同一 READ COMMITTED 事务。
- `dataset/` 不得读取、修改或提交。

---

### Task 1: Inspection Domain and Input Validation

**Files:** 新增 `inspection/domain/Inspection.java`、`InspectionStatus.java`、`InspectionInput.java` 及对应单元测试。

- [ ] 先写状态迁移、首次时间不变、输入 mismatch 和非法输入失败测试并观察 RED。
- [ ] 实现最小 Domain 与基于 Java URI/正则的创建输入校验。
- [ ] 运行 Domain tests，形成独立 commit。

### Task 2: Flyway V2 and Repository

**Files:** 新增 `V2__create_inspections_and_link_results.sql`、Inspection repository/record；新增 migration/repository IT。

- [ ] 先写空库、一致历史回填、冲突历史失败、外键与条件更新测试并观察 RED。
- [ ] 创建 inspections 表，使用 JSON_EXTRACT 回填并在冲突时让迁移失败，最后添加外键。
- [ ] 实现 insert/find/conditional-complete SQL，运行真实 MySQL tests，形成独立 commit。

### Task 3: Create and Query HTTP API

**Files:** 新增 Inspection Controller、Application Service、DTO、异常；扩展统一异常映射与 HTTP IT。

- [ ] 先写 201/200/409、PENDING/COMPLETED/404、稳定 422 和固定 Clock tests 并观察 RED。
- [ ] 实现幂等创建与查询；唯一键失败事务外重新读取赢家。
- [ ] 运行 HTTP/MySQL tests，形成独立 commit。

### Task 4: Atomic Result Intake

**Files:** 修改 `InspectionResultIntakeService`、repositories、错误映射和 Result IT。

- [ ] 先调整旧测试必须创建父 Inspection，并新增不存在、mismatch、原子回滚 tests，观察 RED。
- [ ] 把 Inspection 校验、Result insert 与 conditional complete 编排到同一写事务；replay 不迁移状态。
- [ ] 运行 Result 回归，形成独立 commit。

### Task 5: Concurrency and Full Verification

**Files:** 扩展集成测试；更新 Change 工件和 handoff。

- [ ] 写幂等创建竞争、不同 Result 并发完成、首次 completed_at 不覆盖 tests。
- [ ] 重复运行并发 tests，并运行 `mvn verify`、Python Contract tests、Schema/diff/scope checks。
- [ ] 写入真实调用链、验证、owner task 和 failure exercise；更新为 `review-handoff-ready`。
- [ ] 提交并推送 feature branch，停止实现会话，不合并 main。
