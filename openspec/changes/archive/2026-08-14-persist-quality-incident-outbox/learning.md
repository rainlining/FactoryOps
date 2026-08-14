# 学习计划：2026-08-14-persist-quality-incident-outbox

## 元数据

- `learning_level`: `deep`
- `gate_status`: `completed`

## 编码前必须理解

- 为什么数据库提交后直发 Kafka 会形成双写窗口。
- Outbox 为什么必须与 Incident 使用同一个本地事务。
- immutable canonical payload 与“发布时重建”的区别。
- event ID 主键、aggregate 唯一键与幂等内容核对的不同职责。
- READ COMMITTED 下顺序 replay、并发胜者和败者的真实路径。
- 历史回填为什么必须保留原 occurred_at。
- 本 Change 已解决的持久化一致性，与尚未解决的 Kafka at-least-once 发布问题。

## Code Walkthrough 路线

Review 会话必须沿真实文件覆盖：Result HTTP 入口 → Result Intake 外层事务 → Incident 创建/查找 → Event Factory → Outbox Repository → Flyway 表与回填 → replay/冲突/回滚测试。

## 项目所有者亲自修改任务

为只读 Outbox 查询视图增加 `payload_size_bytes` 派生值并补测试。该值必须按 UTF-8 字节数计算，不得修改 Outbox 表或 canonical payload。

## Failure/Debug Exercise

- 注入故障：暂时让新 Outbox INSERT 使用数据库不允许的 status。
- 预期：HTTP 失败，Inspection 保持 PENDING，Result/Incident/Outbox 均为 0。
- 观察：HTTP 响应、四张表查询和事务日志。
- 常见错误：Incident 已提交但 Outbox 为 0，或吞掉异常后返回成功。
- 复位：恢复 status 为 PENDING，重跑原子性测试和完整构建。
- 完成后应能解释：真正的事务边界在哪里，为什么 Outbox CHECK 能回滚更早的 INSERT。

## Learning Gate

- [x] 能用自己的话解释双写问题和 Transactional Outbox。
- [x] 能沿成功调用链定位事务、事件生成和数据库 INSERT。
- [x] 能定位 replay、冲突与完整性缺失路径。
- [x] 能指出数据库唯一键、外键、状态 CHECK 和待发布索引。
- [x] 完成 owner 修改任务。
- [x] 完成 failure/debug exercise 并根据数据库证据判断。
- [x] review 最终 diff 并明确接受。

## Review/Learning 完成记录

- 项目所有者已完成并接受 `OutboxEventView` owner 修改：通过 `findViewByEventId` 暴露只读视图，并按 UTF-8 字节数计算 `payload_size_bytes`。
- 已完成 Outbox INSERT CHECK 故障实验：Result、Inspection、Incident 和 Outbox 均回滚，Inspection 保持 PENDING。
- 已完成最终 diff review；未修改表结构、canonical payload、事务边界或 Kafka 范围。
- Learning Gate：`completed`。
