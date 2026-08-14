# 验证记录：2026-08-14-persist-quality-incident-outbox

- `status`: `completed`
- `verified_at`: `2026-08-14`
- `dataset_scope`: `untouched`

## 实际命令与结果

1. `python -m unittest discover -s contracts -t . -v`
   - 结果：35 个 Contract 测试通过，0 failure，0 error。
2. `cd backend/business-service && mvn verify`
   - 结果：21 个单元测试和 33 个 MySQL 集成测试通过，0 failure，0 error。
   - Docker Desktop 与 MySQL 8.4 Testcontainers 已真实运行。
3. `git diff --check`
   - 结果：通过。
4. `mvn -Dtest=OutboxEventViewTest -DfailIfNoTests=false test`
   - 结果：owner 修改的 UTF-8 派生值测试通过。
5. `mvn -Dit.test=OutboxMigrationIT verify`
   - 结果：真实 MySQL 迁移与只读视图验证通过。
6. `mvn -Dit.test=InspectionResultHttpIT#outbox_insert_failure_rolls_back_result_incident_and_completion verify`
   - 结果：故障注入测试通过，四个对象整体回滚。

## 关键验证证据

- Java Factory 生成的事件通过冻结的 `quality_incident_opened/v1.0` Schema。
- 新异常结果在同一事务内产生 Result、完成 Inspection、创建 OPEN Incident 和 PENDING Outbox。
- 正常结果不产生 Incident 或 Outbox。
- Outbox CHECK 约束故障会使 Result、Inspection、Incident 与 Outbox 整体回滚。
- 顺序和并发重复输入均只保留一个 Result、Incident 和 Outbox。
- Outbox 缺失或不可变内容冲突会由 replay 完整性校验拒绝，并报告冲突字段。
- V5 将历史 OPEN Incident 回填为唯一 PENDING 事件；SQL payload 与 Java Factory payload 字节一致。
- V5 不修改连接会话时区，而是显式把历史 `TIMESTAMP` 转为 UTC，避免连接池内时区状态不一致。
- `OutboxEventViewTest` 使用包含中文字符的 payload 证明 `payload_size_bytes` 按 UTF-8 字节数而非 Java 字符数计算；只读视图不改变 canonical payload。
- 合并前复验曾捕获一次 replay payload 冲突。根因是 Java `Instant` 保留纳秒，而 MySQL 与事件 Contract 只保留微秒；`QualityIncident.open` 现统一截断为微秒，并由 `normalizes_creation_time_to_mysql_microsecond_precision` 回归测试固定该不变量。

## 已知限制

- 本 Change 不发布 Kafka 消息，也没有 claiming、retry、lease 或 PUBLISHED 状态迁移实现。
- `outbox_events` 当前通过外键限定为 Quality Incident；未来支持其他 aggregate 需要单独迁移外键策略。
- Deep Learning Gate 已完成，项目所有者已接受最终 diff；Change 尚未合并 `main`。
