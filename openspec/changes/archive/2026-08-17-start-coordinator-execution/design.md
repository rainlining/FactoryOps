# Change 设计：启动 Coordinator Execution

## 边界与数据流

- `CoordinatorStartService`：命令校验、Contract 构造、结果分类与重建。
- `MySqlCoordinatorStartRepository`：按 request 查询、Run 行锁与四项写入的单事务。
- Run/Execution Validator：数据库边界前后的最终结构校验。
- MySQL：request 唯一键、FK、条件和事务原子性。

流程：request 查重 → `SELECT Run FOR UPDATE` → 校验初始状态 → 构造并校验 Execution/Run candidate → INSERT Execution → INSERT Execution history → UPDATE Run → INSERT Run history → INSERT start receipt → commit → reload/验证。

## 状态、事务与不变量

- 输入 Run 必须 PENDING revision 0、coordinator null、execution count 0。
- 输出 Run 必须 RUNNING revision 1，started/updated 同一 UTC 时刻，Coordinator 引用新 Execution，count 1。
- Execution 固定 coordinator/attempt 1/task null、PENDING revision 0；provenance 除 prompt 版本外来自 Run。
- receipt 保存 request、Run、Execution 与输入摘要，用于提交结果未知时的幂等恢复。
- 四项领域写入与 receipt 同事务；任何错误全部回滚。

## 并发与失败

同 Run 的行锁决定唯一赢家；不同 request 在赢家提交后读取 RUNNING 并返回 concurrency conflict。相同 request 由 receipt 唯一键恢复并按 payload 摘要区分 identical/conflicting。数据库连接 timeout 可安全使用同 request 重试；本 Change 不做自动 retry。

## 测试策略

纯规则测试命令摘要和初始状态；MySQL 8.4 测试成功、重复/冲突、并发、非法 Contract、history 失败回滚和 receipt 恢复；运行 Contract、Agent Service、Java 全量回归与 Ruff。

## 取舍

- 不串联既有 Run/Execution Service：两个独立事务无法保证聚合间原子性。
- 不把事务塞入领域 Service 私有方法：专用 Repository 明确跨聚合 use case。
- 不引入 Redis lease：瞬时数据库互斥不等于长期 Worker ownership。
