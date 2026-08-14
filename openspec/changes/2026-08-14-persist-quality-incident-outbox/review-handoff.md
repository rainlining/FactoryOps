# Review Handoff：2026-08-14-persist-quality-incident-outbox

## 恢复信息

- 学习等级：`deep`
- 状态：`completed`（本地 Review/Learning 已完成；远端推送仍待网络恢复）
- 分支：`codex/persist-quality-incident-outbox`
- worktree：`C:\Users\小霖\Desktop\work\project2\FactoryOps\.worktrees\persist-quality-incident-outbox`
- base commit：`3e6ed021a0895a691ba70519ebc532503ba99851`
- implementation head：`11ce637`
- 禁止实现会话与 Review/Learning 会话并发修改此 worktree。

## 已实现范围

- 用 V5 创建 `outbox_events` 并为历史 OPEN Incident 回填事件。
- 用 Java Event Factory 生成稳定 event ID、固定六位 UTC 微秒时间和 canonical JSON。
- 在既有 Result Intake 写事务内原子保存 Incident 与 PENDING Outbox。
- replay 必须找到同一事件，并逐项核对不可变身份和内容。
- 数据库、并发、回滚、迁移及 Java→Schema Contract 均有自动化测试。

非目标：Kafka Producer/Consumer、发布抢占、重试、锁、PUBLISHED 迁移、Incident 状态迁移。

## 建议阅读顺序与真实调用链

1. HTTP 入口：`InspectionResultController.accept`。
2. 事务编排：`InspectionResultIntakeService.accept`；`TransactionTemplate` 包住 Result、Inspection、Incident、Outbox 写入。
3. Incident 分支：`QualityIncidentService.openOrFind` 创建新 Incident；`findForReplay` 处理重复结果。
4. 事件生成：`QualityIncidentOpenedEventFactory.create`。
5. 持久化和回放校验：`OutboxEventJdbcRepository.insert`、`requireMatching`。
6. 数据库边界：`V5__create_and_backfill_outbox_events.sql`。
7. 成功、回放、并发和回滚：`InspectionResultHttpIT`。
8. 历史迁移与精确 payload：`OutboxMigrationIT`。

成功链：POST Result → Contract 校验 → Result Intake 事务 → Result INSERT → Inspection COMPLETE → Incident INSERT → Outbox INSERT → commit。

重复链：相同 Result → replay 比较 → 读取 Incident → 重建期望事件 → `requireMatching` → 返回相同 Incident ID，不新增 Outbox。

失败链：Outbox INSERT 违反 CHECK → JDBC 异常越过服务边界 → 外层事务回滚此前所有写入。Outbox 缺失或内容冲突则在 replay 时抛出 `OutboxIntegrityException`。

## 验证与限制

验证命令和真实结果见 `verification.md`。本地 Docker 已运行，全量 Java 集成测试已实际执行。Kafka 发布可靠性不属于此 Change。

## Owner 修改任务

为只读 Outbox 查询视图增加 `payload_size_bytes` 派生值并补测试。必须按 UTF-8 字节数计算，不修改表结构或 canonical payload。

## Failure/Debug Exercise

临时让新 Outbox INSERT 使用数据库不允许的 status；执行异常结果写入，观察 HTTP 失败且 Inspection 仍为 PENDING、Result/Incident/Outbox 均为 0。恢复 PENDING 后重跑原子回滚测试和完整构建。

本地 Review 会话已完成 Walkthrough、owner 修改、故障实验、最终 diff review 与 Learning Gate，因此 Change 已在本地记录为 `completed`。

## Review/Learning 完成记录

- 项目所有者已接受最终 diff。
- Owner 修改已提交于 `11ce637`：新增 `OutboxEventView`，通过 `OutboxEventJdbcRepository.findViewByEventId` 提供只读查询，并按 UTF-8 字节数计算 `payload_size_bytes`。
- 故障实验已完成：临时拒绝 Outbox INSERT 的 `status` 后，Result、Inspection、Incident、Outbox 均未留下数据，Inspection 保持 PENDING。
- 验证结果：Java 单元测试 20/20、MySQL 集成测试 33/33、Python Contract 35/35，`git diff --check` 通过，`dataset/` 未修改。
- Learning Gate：`completed`。
- 集成限制：当前本地分支尚未推送远端，也未合并 `main`；推送成功后仍需按项目流程执行集成操作。
