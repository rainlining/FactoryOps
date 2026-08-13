# Change 提案：2026-08-13-establish-quality-incident

## 元数据

- `change_id`: `2026-08-13-establish-quality-incident`
- `status`: `design-reviewed`
- `learning_level`: `deep`
- `first_deep_reference`: `2026-08-13-establish-inspection-lifecycle`
- `depends_on`: `[2026-08-13-establish-batch-lifecycle]`
- `spec_refs`: `[inspection-result-intake, inspection-lifecycle, batch-lifecycle]`
- `implementation_session`: `current Codex task`
- `review_session`: `pending`

## 为什么要做

系统已经能保存不可变 Vision Result 并管理 Batch，但异常 Result 仍只是一条模型观察，没有一张可供 Coordinator、Agent、审批和审计持续引用的业务问题单。若 Incident 依赖后续调用或消息才能创建，会出现异常已经入库却无人处置的半完成状态。

## 范围

- 本 Change 唯一核心能力：将合法异常 Result 原子地登记为唯一 `OPEN` Quality Incident。
- Incident 以固定算法从 Result 身份派生 ID，并保存 Batch、Inspection、Result 的不可变证据引用。
- Result Intake 响应异常时返回稳定 `incident_id`，正常时返回 `null`。
- 提供单个 Incident 查询 API。
- V4 为历史异常 Result 补建 Incident，并继承 Result 创建时间。

## 非目标

- Incident 调查、分派、解决、关闭、重开、合并、列表或搜索。
- 自动 HOLD Batch、权威 Result 选择、连续缺陷判断。
- Coordinator、Agent Runtime、Prompt、Kafka、Outbox、Consumer。
- 审批、权限、审计和数据库自动重试。

## 预期影响

- 新增规格：`quality-incident`。
- 修改规格：`inspection-result-intake` 响应增加 `incident_id`，并增加三对象原子事务要求。
- 代码区域：Java Result Intake、Quality Incident Domain/Application/Repository/API、Flyway V4、MySQL/Testcontainers 测试。

## 依赖与顺序

- 前置：不可变 Result、Inspection 生命周期和 Batch 归属均已生效。
- 后续：Transactional Outbox 可以可靠发布 Incident；Coordinator Run 可以以 Incident 为工作流主线。

## 学习等级理由

Repository、HTTP 查询和基础唯一键复用既有 deep 模式；但本 Change 首次引入“一个输入同时产生 Result、Inspection Completion、Incident 三个原子业务事实”，以及派生身份与业务唯一键的双重保护，因此保持 `deep`。

## 验收摘要

- 技术验收：Domain、HTTP Contract、V4 回填/约束、真实 MySQL 并发与三对象原子回滚测试通过。
- 学习验收：能沿成功与失败链定位事务、派生 ID、唯一键和证据关系，完成查询派生字段修改与故障实验。
