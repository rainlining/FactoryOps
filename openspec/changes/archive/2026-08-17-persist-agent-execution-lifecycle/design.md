# Change 设计：Execution 生命周期持久化

## 边界与数据流

- Service：创建/迁移编排、幂等分类、Contract 重建。
- rules：纯状态、时间、result/failure 规则。
- Repository：SQL、父关系校验、事务、条件 UPDATE。
- MySQL：唯一键、FK、snapshot/history 原子性。

创建链：按 key 查询 → 构造 Contract → Validator → 事务锁定 Run/Task 并校验 role/run → snapshot + initial history。迁移链：按 request 查询 → current snapshot → rules → candidate Validator → 条件 UPDATE + history。

## 数据模型与不变量

- `agent_executions` 保存身份、provenance、input、lifecycle、result/failure；引用数组使用 JSON。
- `agent_execution_transitions` append-only 保存 request、revision、actor/reason 和终态摘要。
- `(run_id, agent_role, task_id, attempt)` 由 Contract key 唯一表达；数据库以 `execution_key` 唯一。
- Specialist Task 必须同 Run 且 target role 匹配；Coordinator task_id 必须为空。
- identity/provenance/input 不可变；updated_at 单调；终态不可离开。

## FK 与升级

先创建 Execution 表及其 Run/Task FK，再 ALTER Run/Task 增加反向 FK。业务创建顺序固定为 Run → Coordinator Execution → Task → Specialist Execution。既有孤立逻辑引用导致 migration 失败，这是数据审计信号，不自动清除。

## 并发、失败与测试

唯一键竞争后重读赢家；迁移条件为 id/status/revision；history 失败回滚 snapshot。纯规则单测覆盖状态，MySQL 8.4 覆盖 migration、父关系、幂等、并发、失败注入、FK 和 Contract 重建。

## 取舍

- 不用 JSON 整行，保留查询/约束能力。
- 不用 trigger 状态机，避免与 Validator 双重语义。
- 不在此 Change 实现 Worker lease；持久事实与执行 ownership 分离。
