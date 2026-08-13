# Change 设计：2026-08-13-establish-batch-lifecycle

## 设计目标

建立真实 Batch 聚合，使 Inspection 具有不可变批次归属，并让首次 HOLD 在并发下保留唯一、不可覆盖的时间、原因和异常证据。

## 边界与所有权

- Java Batch Domain 拥有状态迁移、原因与证据形状规则；Application Service 拥有事务、证据关系验证和结果分类。
- MySQL 拥有唯一键、外键、CHECK、条件更新和父行锁最终防线。
- Vision Result 保持不可变；本 Change只读取其异常事实，不选择权威 Result。
- Agent、Incident 和客户端不得绕过 Java Business API 修改 Batch。

## 领域模型

- Batch 不可变身份：`batch_id`、`product_code`、`production_line`、`kind`。
- `kind`: `PRODUCTION | LEGACY_UNASSIGNED`；外部只能创建 `PRODUCTION`。
- 状态：`OPEN → HELD → RELEASED`；RELEASED 为终态。
- 外部 HOLD 原因：`QUALITY_ANOMALY | MANUAL_QUALITY_HOLD | PROCESS_ANOMALY`。
- 内部 RELEASE 原因：`MANUAL_REVIEW_PASSED | RECHECK_PASSED | DISPOSITION_APPROVED`。
- `reason_detail` 可选，trim 后非空，最长 500；命令幂等比较使用规范化快照。
- `QUALITY_ANOMALY` 必须同时引用 `inspection_id` 与 `result_id`；其他原因禁止证据字段。

ID Contract：Batch 为 `^[A-Z0-9][A-Z0-9-]{0,63}$`，`SYS-` 保留；Product 为 `^[A-Z0-9][A-Z0-9._-]{0,63}$`，Production Line 为 `^[A-Z0-9][A-Z0-9-]{0,63}$`。不自动修剪标识符、转换大小写或替换字符。

## API 与数据流

- `POST /api/v1/batches`：首次 201；相同身份 200 replay；同 ID 不同身份 409 `batch_identity_conflict`。
- `GET /api/v1/batches/{id}`：返回完整生命周期快照；不存在 404 `batch_not_found`；占位 Batch 可查询。
- `POST /api/v1/batches/{id}/hold`：首次 200 applied；相同原因/证据 200 replay；不同命令 409 `batch_command_conflict`；RELEASED 为 409 `invalid_batch_transition`；占位对象为 409 `batch_not_actionable`。
- 不提供 RELEASE HTTP 路由；内部 Application Command 与集成测试覆盖其语义。

Inspection 创建新增必填 `batch_id`。已有 Inspection 先比较 `inspection_id + batch_id + image_uri + sha256`：完全相同即 replay，即使 Batch 后来 RELEASED；不同即 409。全新 Inspection 在写事务中 `SELECT Batch FOR UPDATE`，只允许 `PRODUCTION + OPEN/HELD`，再插入。

QUALITY_ANOMALY HOLD 在一个 READ COMMITTED 写事务中先锁 Batch，再读取不可变 Inspection/Result，验证 Result 属于 Inspection、Inspection 属于 Batch 且 `is_anomaly=true`，最后以 `WHERE kind='PRODUCTION' AND status='OPEN'` 条件更新 Batch。

## 状态、事务与不变量

- `OPEN` 的 hold/release 字段全空；`HELD` 的 hold 时间/原因存在、release 为空；`RELEASED` 的 hold/release 时间和原因均存在。
- 所有运行期时间由应用 UTC `Clock` 产生；重放不覆盖首次时间或原因。
- 相同 HOLD/RELEASE 命令是 replay；同目标状态但原因或证据不同是 conflict。
- Batch 状态命令及跨对象写事务统一遵循锁顺序 `Batch → Inspection → Result`。
- HOLD 单行状态竞争使用条件更新；Inspection 创建的“检查父状态 + 插入子行”使用父 Batch 行锁关闭 RELEASE 并发窗口。
- 数据库外键保证证据对象存在；Java 保证证据间关系及 anomaly 语义。

## Schema 与迁移

V3 创建 `batches`，包含身份、kind/status、created/held/released 时间、原因详情及 hold Inspection/Result 的 hash+原文。Inspection 新增非空 `batch_id_hash BINARY(32)` 与 `batch_id VARCHAR(64)`。

迁移顺序：创建 Batch 表（暂不加证据 FK）→ 插入 `SYS-LEGACY-UNASSIGNED` → Inspection 增加可空字段 → 回填历史 → 改为 NOT NULL → 添加 Inspection→Batch FK → 添加 Batch evidence→Inspection/Result FK。占位对象为 `LEGACY_UNASSIGNED + RELEASED`，三个时间使用同一迁移时间，产品/产线为 `SYS-LEGACY`，hold/release 原因均为仅迁移可用的 `MIGRATED_LEGACY_DATA`。所有删除行为为 RESTRICT。

## 失败路径

- 非法/保留 Batch ID、产品或产线：422 稳定错误；未知字段或 malformed：400。
- Batch/证据对象不存在、证据关系错误或 Result 非 anomaly：按设计分别返回 404/422，Batch 不变化。
- 并发创建唯一键失败：退出失败事务，新只读事务读取赢家并分类 replay/conflict。
- HOLD 条件更新 0 行：重新读取并分类 replay/conflict/invalid transition；不得覆盖赢家。
- Insert、Update 或 Commit 失败：事务回滚，无部分状态。本 Change 不自动 retry，调用方以完全相同幂等请求重试。
- Docker 不可用时不得声称 MySQL、迁移、HTTP 或并发测试通过，也不得进入 handoff。

## 测试与可观测性策略

- Domain：格式、状态—时间组合、原因规范化、证据形状、HOLD/RELEASE/replay/conflict。
- HTTP：创建/查询/HOLD 的成功、重放、冲突、非法输入与稳定错误；确认 RELEASE 路由不存在。
- MySQL：V3 回填、NOT NULL、外键/CHECK、事务回滚、并发创建/HOLD、Inspection 与 RELEASE 竞争。
- 回归：完整 Java、Python Vision Contract、OpenSpec、diff 和 dataset scope。
- 证据：HTTP disposition、SQL 影响行数、数据库首次时间/原因/evidence、Flyway 日志；不记录完整 Vision JSON。

## 方案比较与决定

- 采用最小 Batch 聚合，不同时建立 Product/Order。
- RELEASE Domain 能力存在但不暴露 HTTP，避免绕过未来 Approval。
- HOLD 采用条件更新而非通用 version；Inspection 创建采用父行锁而非仅 Java 预查。
- 历史数据绑定显式系统占位 Batch，不猜测真实归属，也不允许运行期继续写入占位对象。
- 精确 Result 证据优于只引用 Inspection，保证解释不随后续 Result 集合变化。

## 连续 Apply 计划

1. Batch Domain 与 Contract tests。
2. V3 Migration、约束与 Repository tests。
3. Batch 创建/查询 API 与并发创建。
4. Inspection Batch 归属、replay 身份与父行锁。
5. HOLD 原因/证据验证、条件更新与并发分类。
6. 内部 RELEASE 及 Inspection/Release 竞争。
7. 全量回归、OpenSpec、handoff、提交和推送。
