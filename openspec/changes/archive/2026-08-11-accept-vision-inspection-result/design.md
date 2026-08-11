# Change 设计：2026-08-11-accept-vision-inspection-result

## 架构与边界

一个 Spring Boot 模块化单体，当前仅有 `inspection` 模块：`api → application → domain ← infrastructure`。Domain 不依赖 Spring/JDBC；API 使用共享 Schema；Infrastructure 负责 MySQL。

## 成功调用链

```text
HTTP bytes → Jackson JsonNode → exact version → Draft 2020-12 Schema
→ DTO mapping → Domain factory(BigDecimal invariant)
→ canonical JSON + SHA-256
→ IntakeService → TransactionTemplate(READ_COMMITTED)
→ SELECT by result identity hash → INSERT or compare
→ 201 created / 200 replayed
```

## 失败路径

- JSON parse：400。
- Schema/domain issue：422，固定第一 issue。
- 已存在不同 hash：409。
- 并发 INSERT DuplicateKeyException：写事务退出并回滚；外层 catch 后开启新只读事务，重新查询赢家并比较。
- result ID hash 碰撞：原文不同即按 identity-hash collision 失败，不把两个 ID 当同一身份。
- 数据库不可用：500，事务无部分写入；不在本 Change 内自动 retry。

## 数据模型

`vision_inspection_results` 保存原始 ID TEXT、ID SHA-256 BINARY(32)、关键 provenance、规范化 decimal TEXT、boolean、canonical payload JSON、payload hash BINARY(32)、produced/created timestamp。`result_id_hash` 唯一，`inspection_id_hash` 普通索引。所有列无 UPDATE 路径。

## 事务不变量

- 写事务短小，隔离级别 READ COMMITTED。
- DuplicateKeyException 后不在失败事务内查询。
- 任何 replay/conflict 都不更新赢家。
- 关系列、canonical payload 和 hash 来自同一已校验输入。

## 测试

- 纯单元：canonicalizer、Domain invariant、错误排序。
- Web slice/MockMvc：201/200/400/422/409 契约。
- Testcontainers MySQL：Flyway、repository、事务、重复、冲突、同 inspection 多结果、并发竞态、不可覆盖。

## 方案取舍

- 采用模块化单体而非微服务。
- 采用 JdbcTemplate 而非 JPA，暴露 SQL/事务语义。
- 采用 TransactionTemplate 而非多 Bean AOP 传播，显式展示事务生命周期。
- 采用预查询 + INSERT + 唯一键异常恢复，而非原子 no-op upsert。
- Decimal/ID 使用原文/规范化文本与派生 hash，避免悄悄收紧已冻结 Contract。

## 内部任务/commit 边界

1. OpenSpec 与 Java build baseline。
2. Schema/domain/canonicalization。
3. HTTP API/error contract。
4. Flyway/JdbcTemplate/transactions。
5. MySQL concurrency tests、verification 与 handoff。
