# Change 设计：2026-08-13-establish-inspection-lifecycle

## 设计目标

建立可创建、查询并由第一份匹配 Result 原子完成的 Inspection 聚合；后续 Result 可保存但不能重开或覆盖首次完成时间。

## 边界与所有权

- Java Inspection 模块拥有聚合规则、API、事务编排和错误映射。
- Repository 只执行持久化操作，不自行决定业务错误。
- MySQL 负责唯一键、外键、状态约束与条件更新最终防线。
- 本 Change 调用已生效的 Vision Contract Validator，不修改 Contract 1.0。
- 不建立 Batch、Incident、Kafka、Agent 或权限边界。

## 数据流或控制流

创建：`POST inspections → 输入校验 → READ COMMITTED 预查询 → INSERT`；唯一键竞争必须退出失败事务，再以新读事务读取赢家，相同输入返回 replay，不同输入返回 409。

查询：`GET inspection → hash 查询 → 原始 ID 碰撞防御比较 → DTO`；不存在返回 404。

结果：事务外依次执行 JSON、Schema、Domain 校验；写事务内读取 Inspection、比较原始 ID 与图片身份、处理 result replay/conflict、插入新 Result、条件更新状态并提交。

## 状态、事务与不变量

- 状态只有 `PENDING → COMPLETED`，不可取消、重开或回退。
- Result 插入与首次完成必须同事务提交，禁止半完成状态。
- `completed_at` 由注入的应用 UTC `Clock` 产生；只有 `WHERE status='PENDING'` 更新成功者可写入。
- 不同 Result 并发都可保存；后到事务更新 0 行后必须确认已 COMPLETED。
- 相同 Result replay 不重复推进状态。
- 图片 URI 与 SHA 按原始字符串精确比较，不自动规范化。

## 数据模型与迁移

V2 创建 `inspections(inspection_id_hash, inspection_id, expected_image_uri, expected_image_sha256, status, created_at, completed_at)`。hash 为主键，原文保留用于碰撞防御。V2 从 V1 `canonical_payload` 提取图片身份，按 inspection 分组检查冲突，以组内最早 Result `created_at` 回填两个时间，再添加 Result→Inspection 外键。

## 失败路径

- 非法创建输入：422 稳定 code/path，不访问 Repository。
- 创建身份冲突：409，无覆盖。
- Result 的 Inspection 不存在或图片不匹配：422，事务回滚且 Result 不入库。
- Result 冲突：409，聚合状态不变。
- 插入、状态更新或提交失败：整个 Result/Inspection 事务回滚。
- 数据库瞬时故障：本 Change 不自动 retry；调用方以同一幂等请求重试。
- 历史数据图片冲突：Flyway 启动失败，不静默选择。

## 测试与可观测性策略

- Domain：状态迁移、首次时间不变、图片匹配、非法状态时间组合。
- HTTP：创建 201/replay 200/conflict 409、查询 PENDING/COMPLETED/404、稳定 422。
- MySQL：空库 V2、一致历史回填、历史冲突失败、外键、原子回滚、创建与完成并发。
- 回归：现有 Java Result Intake 和 Python Vision Contract 全套测试。
- 证据：HTTP 响应、数据库行/时间、Flyway 日志、并发更新结果与测试报告。

## 方案比较与决定

- 采用现有 Spring Boot 模块化单体，避免跨服务分布式事务。
- 采用 SQL 条件更新而非 `SELECT FOR UPDATE`，让数据库直接表达一次性状态迁移且不串行化全部 Result。
- 采用应用 UTC Clock 而非数据库时间，便于固定时钟测试及未来统一审计/事件时间。
- 采用历史回填而非只支持空库，确保 V1 数据可解释升级。

## 连续 Apply 计划

1. OpenSpec/迁移测试：冻结规格和 V1→V2 场景。
2. Domain/API TDD：Inspection 聚合、输入校验、创建与查询。
3. Persistence TDD：V2、Repository、约束及历史回填。
4. Transaction TDD：把 Result Intake 重构为跨表原子事务。
5. Concurrency/回归：创建竞争、不同 Result 完成竞争与全套测试。
6. Verification/handoff：范围检查、提交、推送并停在 review-handoff-ready。
