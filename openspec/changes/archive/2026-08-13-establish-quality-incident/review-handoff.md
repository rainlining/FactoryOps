# Review Handoff：2026-08-13-establish-quality-incident

## 恢复信息

- 学习等级：`deep`
- 分支：`codex/establish-quality-incident`
- Worktree：`C:\Users\小霖\Desktop\work\project2\FactoryOps\.worktrees\establish-quality-incident`
- Base：`6b15f45`
- 实现提交：`a8cb1af`（本 handoff 另有后续文档提交）
- 禁止实现与 Review 会话并发修改该 worktree。

## 已实现与非目标

- 异常 Result、Inspection Completion、唯一 OPEN Incident 在同一事务提交或回滚。
- 稳定派生 Incident ID、Result 一对一唯一约束、V4 历史回填与证据链外键。
- Result 响应返回可空 `incident_id`；Incident 支持单体 GET 和稳定 404。
- 未实现状态迁移、自动 HOLD、Kafka/Outbox、Agent、审批、权限、列表或合并。

## 建议阅读顺序与调用链

1. `InspectionResultController#accept`：Result HTTP 入口和响应。
2. `VisionInspectionContractValidator#validate`：证明 `is_anomaly` 与分数阈值一致。
3. `InspectionResultIntakeService#accept`：最外层写事务、replay 与失败传播。
4. `QualityIncidentService#openOrFind/findForReplay`：异常登记规则。
5. `QualityIncidentId#fromResultId` 与 `QualityIncident#open`：派生身份和 Domain 不变量。
6. `QualityIncidentJdbcRepository` 与 V4：SQL、唯一键、证据外键与历史回填。
7. `QualityIncidentController` → `QualityIncidentQueryService`：只读查询链。
8. `InspectionResultHttpIT`：异常/正常、replay、查询、404、Batch 不变和原子回滚证据。

成功链：Controller → Validator → Intake 写事务 → Inspection 验证/完成 → Result INSERT → Incident Service → Incident INSERT → COMMIT → CREATED + incident_id。

失败链：Incident INSERT 的 CHECK 故障向 Intake 抛出，TransactionTemplate 回滚 Result、Inspection Completion 和 Incident，HTTP 不返回成功。

## 验证与剩余门禁

- Java 45 项、Python 17 项通过；真实 Docker/MySQL 和 V1→V4 已执行。
- Java 已统一格式化，无压缩单行代码。
- Review 会话仍需完成真实 Walkthrough、owner 修改、故障实验和最终 diff 接受；完成前不得合并 main。

## Learning Gate

- Owner 修改：为 Incident 查询响应增加派生 `result_origin_kind`；在只读 Query Service 中组合 Result Repository，至少覆盖两个 origin，不修改 Incident 表。
- Failure exercise：注入 Incident INSERT 数据库失败，观察 Result=0、Incident=0、Inspection=PENDING 且 `completed_at=null`；复位后重跑测试。
