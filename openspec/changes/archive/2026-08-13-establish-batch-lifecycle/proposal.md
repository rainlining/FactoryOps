# Change 提案：2026-08-13-establish-batch-lifecycle

## 元数据

- `change_id`: `2026-08-13-establish-batch-lifecycle`
- `status`: `archived`
- `learning_level`: `deep`
- `first_deep_reference`: `2026-08-13-establish-inspection-lifecycle`
- `depends_on`: `[2026-08-13-establish-inspection-lifecycle]`
- `spec_refs`: `[inspection-lifecycle, inspection-result-intake]`
- `implementation_session`: `current Codex task`
- `review_session`: `completed`

## 为什么要做

当前系统能创建 Inspection 并接收 Vision Result，但不知道质检属于哪个生产批次，也没有可由确定性 Java 规则执行的 `HOLD_BATCH` 目标。若直接建立 Incident 或 Agent Tool，Agent 只能生成文字建议，无法安全改变真实业务状态。

## 范围

- 本 Change 唯一核心能力：建立可创建、查询、冻结并在内部释放的 Batch 聚合，使 Inspection 永久归属于一个 Batch。
- 建立 `OPEN → HELD → RELEASED` 单向状态机、原因快照和精确异常证据。
- 对外提供 Batch 创建、查询和 HOLD API；RELEASE 仅保留内部能力。
- V3 创建 Batch Schema，将历史 Inspection 归入系统占位 Batch，并建立外键。
- 修改 Inspection 创建 Contract，强制真实 `batch_id`，并关闭与 RELEASE 的并发窗口。

## 非目标

- Product、Order、Quality Incident、Approval、Audit。
- RELEASE HTTP API、多轮 HOLD/RELEASE、删除或转移 Inspection。
- Kafka、Outbox、Redis、Agent Tool、权限、列表与分页。
- 权威 Vision Result 选择。

## 预期影响

- 新增规格：`batch-lifecycle`。
- 修改规格：`inspection-lifecycle` 增加不可变 Batch 归属。
- 代码区域：Java Batch/Inspection 模块、Flyway V3、MySQL/Testcontainers 测试。
- Inspection 创建 API 是明确的破坏性变更：新请求必须提供 `batch_id`。

## 依赖与顺序

- 前置：Inspection 聚合、不可变 Vision Result 及其关联已生效。
- 后续：异常 Result 创建 Quality Incident、Batch Release Approval、Transactional Outbox、Agent HOLD Tool。

## 学习等级理由

CRUD、JdbcTemplate、TransactionTemplate、派生 hash 主键和幂等创建复用既有 deep 模式；但本 Change 首次引入生产处置状态机、带证据的幂等命令、条件更新与父行锁的适用边界、Inspection/Release 跨表并发不变量，因此保持 `deep`。

## 验收摘要

- 技术验收：Domain、HTTP Contract、V3 迁移、外键/CHECK、事务回滚及真实 MySQL 并发测试通过。
- 学习验收：能解释 Batch 业务边界、状态机、证据链、条件更新与父行锁，完成 owner 修改和并发 HOLD 故障实验。
