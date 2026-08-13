# Review Handoff：2026-08-13-establish-inspection-lifecycle

## 恢复信息

- 学习等级：`deep`
- Feature branch：`agent/establish-inspection-lifecycle`
- Worktree：`C:\Users\小霖\Desktop\work\project2\FactoryOps\.worktrees\establish-inspection-lifecycle`
- Base commit：`2caf1c9e0af36d5624af02db0b0493e85c9b8911`
- Implementation head commit：`2b34e9c`（handoff 文档提交是其直接后继，恢复时以远端 branch head 为准）
- 状态：`review-handoff-ready`
- 禁止实现会话与 Review/Learning 会话并发修改本 worktree。

## 已实现范围与非目标

新增 Inspection 的创建、幂等重放、身份冲突、查询及 `PENDING → COMPLETED` 生命周期；V2 从历史 Result 回填父实体并建立外键；Result 接收校验父实体和图片身份，并在一个 READ COMMITTED 事务中完成父行与保存子行。未实现取消、重开、权威 Result、列表、Kafka、Outbox、Agent、权限或自动重试。

## 建议阅读顺序与真实符号

1. HTTP 入口：`InspectionLifecycleController.create/get`、已有 `InspectionResultController.accept`。
2. 创建/查询编排：`InspectionApplicationService.create/get/compare`。
3. 聚合规则：`Inspection.pending/restore/complete`、`InspectionInput.firstMismatch`。
4. Result 原子编排：`InspectionResultIntakeService.acceptValidated`。
5. 数据库边界：`InspectionJdbcRepository.insert/find/completePending`、`VisionInspectionResultJdbcRepository.insert`。
6. Schema：`V2__create_inspections_and_link_results.sql`。
7. 测试：`InspectionTest` → `InspectionLifecycleHttpIT` → `InspectionResultHttpIT` → `InspectionMigrationIT`。

## 成功调用链

`POST /api/v1/inspection-results` → JSON/Schema/Domain Validator → `InspectionResultIntakeService.acceptValidated` → 读取并核对 Inspection → `completePending(... WHERE status='PENDING')` → 插入 Result → 同一事务 commit。并发后到者等待父行锁，条件更新返回 0，随后仍保存自己的不同 Result，且不覆盖 `completed_at`。

## 失败与恢复调用链

- 不存在/图片不匹配：事务内抛出对应异常，HTTP 映射 422，Result 不入库。
- Result insert 失败：此前父行更新随事务回滚；`result_insert_failure_rolls_back_inspection_completion` 用临时 CHECK 约束提供真实证据。
- 创建唯一键竞争：失败事务退出后在新只读事务读取赢家；相同输入 replay，不同输入 409。
- V2 历史身份冲突：冲突组不回填，添加 FK 失败并阻止应用带错误历史启动。
- 实施中发现“先插子行再更新父行”会因外键共享锁升级导致并发死锁，因此最终顺序改为先锁/条件更新父行、再插入子行。

## 验证

实际命令和结果见 `verification.md`。最终 fresh 验证已运行：Java 35 项、Python 17 项均为 0 failure/error，Git whitespace 与 dataset scope 检查通过。

## Review/Learning 任务

- Owner 修改：为 Inspection 查询响应增加 `result_count`，覆盖 PENDING、首次完成和多 Result；不得修改状态迁移或写事务。
- Failure/debug exercise：暂时移除 `completePending` SQL 的 `AND status='PENDING'`，以两份不同 Result 复现首次完成时间被覆盖，再恢复条件并验证。
- Learning Gate：能够解释设计、沿成功与失败调用链定位、完成修改与实验、指出事务/幂等实际位置，并接受最终 diff 后才可 completed/archived/merge main。

## Review 完成记录

2026-08-13，项目所有者完成调用链、失败路径和最终 diff review，并明确接受 Change。`result_count` 由 Review 会话代写；故障 SQL 已注入并恢复，但因 Docker 不可用未实际观察时间覆盖。详细状态见 `learning.md` 与 `verification.md`。

## 剩余风险

- 当前 API 输入校验错误粒度较粗，非法创建统一为 `invalid_inspection_input`；可在后续独立 Contract Change 中细化，不影响本 Change 的生命周期不变量。
- MySQL DDL 非完全事务化；冲突迁移失败后应恢复备份/清理失败对象再修复历史数据，不应直接重跑生产库。
