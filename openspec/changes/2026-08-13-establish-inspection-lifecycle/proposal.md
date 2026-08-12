# Change 提案：2026-08-13-establish-inspection-lifecycle

## 元数据

- `change_id`: `2026-08-13-establish-inspection-lifecycle`
- `status`: `review-handoff-ready`
- `learning_level`: `deep`
- `first_deep_reference`: `2026-08-11-accept-vision-inspection-result`
- `depends_on`: `[2026-08-10-define-vision-inspection-contract, 2026-08-11-accept-vision-inspection-result]`
- `spec_refs`: `[vision-inspection-contract, inspection-result-intake]`
- `implementation_session`: `current Codex task`
- `review_session`: `pending`

## 为什么要做

现有 `inspection_id` 只是 Vision Result 中的字符串，尚无真实业务 Inspection。系统需要先创建带预期图片身份的质检任务，再以原子事务接收结果并完成任务，才能为后续 Incident、Kafka 和 Agent 建立可靠业务事实。

## 范围

- 本 Change 唯一核心能力：建立 Inspection 的创建、查询与不可逆完成生命周期。
- `POST /api/v1/inspections` 和 `GET /api/v1/inspections/{inspection_id}`。
- `PENDING → COMPLETED` 聚合状态迁移。
- Result 必须关联已存在且图片身份匹配的 Inspection。
- Result 插入与首次完成状态在同一 MySQL 事务提交。
- Flyway V2 历史回填、数据一致性检查与外键。

## 非目标

- Batch/Product/Order/Incident 聚合。
- 取消、重开、状态历史、权限和审计。
- Kafka、Outbox、Redis、Agent Runtime、Vision Service。
- 权威 Result 选择、列表/筛选/分页 API、应用内部数据库自动重试。

## 预期影响

- 新增规格：`inspection-lifecycle`。
- 修改规格：`inspection-result-intake` 增加业务前置条件和原子完成语义。
- 代码区域：现有 Java Inspection 模块、Flyway、Testcontainers 集成测试。
- Vision Inspection Contract 1.0 不修改。

## 依赖与顺序

- 前置：不可变 Vision Result Contract 与 Intake 已生效。
- 后续：异常结果创建 Quality Incident、Transactional Outbox 与 Kafka Event。

## 学习等级理由

JdbcTemplate、TransactionTemplate、哈希派生键和幂等创建复用首次 deep Change 的模式；但本 Change 新增真实聚合、跨表原子不变量、不同 Result 并发竞争一次状态迁移、历史回填与外键迁移，属于新的关键事务与失败语义，因此保持 `deep`。

## 验收摘要

- 技术：Domain、HTTP Contract、Flyway V1→V2、真实 MySQL 原子性与并发测试通过。
- 学习：解释聚合/事务/数据库三层不变量，定位四条调用链，完成 owner 修改和条件更新故障实验。
