# Change 提案：2026-08-11-accept-vision-inspection-result

## 元数据

- `change_id`: `2026-08-11-accept-vision-inspection-result`
- `status`: `applying`
- `learning_level`: `deep`
- `first_deep_reference`: `N/A`
- `depends_on`: `[2026-08-10-define-vision-inspection-contract, 2026-08-11-streamline-change-implementation-learning-handoff]`
- `spec_refs`: `[vision-inspection-contract]`
- `implementation_session`: `current Codex task`
- `review_session`: `pending`

## 为什么要做

Vision Inspection Contract 1.0 已冻结，但还没有真实业务 Consumer。FactoryOps 需要第一个 Java/MySQL 调用链，把视觉结果转换为不可变且可并发安全重试的业务输入事实。

## 范围

- `POST /api/v1/inspection-results`。
- 共享 JSON Schema 校验、Java Domain 跨字段校验和稳定错误响应。
- 规范化 JSON 与 SHA-256 内容身份。
- Flyway MySQL Schema、JdbcTemplate Repository、TransactionTemplate + READ COMMITTED。
- 首次创建、相同重放、身份冲突、并发竞态与真实 MySQL 集成测试。
- 最小 Spring Boot 模块化单体，只建立 Inspection Result 模块。

## 非目标

- Kafka、Outbox、Redis、Agent、Vision Service。
- Inspection 生命周期、Batch/Order/Incident、权威结果选择。
- GET/PUT/DELETE、认证授权、微服务拆分。

## 技术基线

- Java 17、Maven、Spring Boot 4.1.0。若后续能力确实需要 Java 21 特性或依赖，再通过独立 Change 升级运行时。
- Spring Web/JDBC、Flyway、MySQL Connector/J、Testcontainers MySQL。
- NetworkNT JSON Schema Validator 3.0.6（Draft 2020-12 / Jackson 3）。
- MySQL 8.4 LTS container。

版本依据：Spring 官方 System Requirements 与 NetworkNT 官方 README/release 信息，核查日期 2026-08-11。

## 学习等级理由

这是 FactoryOps 首次 Java Domain、MySQL Schema/Index、显式事务边界和数据库并发幂等实现，属于 `first deep`。实现会话连续交付到 `review-handoff-ready`；独立 Review/Learning 会话完成 Walkthrough、owner 修改与故障实验。

## 验收摘要

- 技术：单元、HTTP Contract、Flyway/MySQL 集成、重复与并发测试通过。
- 学习：真实调用链、事务回滚/新事务恢复、唯一约束、owner 修改和 failure exercise。
