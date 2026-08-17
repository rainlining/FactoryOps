# Change 设计：Coordinator Dispatch Task

## 边界与数据流

`CoordinatorTaskDispatchService` 负责命令摘要、Task Contract 构造与结果分类；`MySqlCoordinatorTaskDispatchRepository` 在一个事务中锁 Execution/Run、校验父关系、插入 Task/依赖/history；既有 Task Service 负责读取重建 Contract。

流程：按 request 查重 → 锁 Coordinator Execution → 锁 Run → 校验 Execution RUNNING、role/run → 构造并验证 Task → 插入 Task/依赖/初始 history → commit → reload。

## 不变量与失败

Task 初始为 PENDING revision 0、attempt 0、无 current Execution；`created_by_execution_id` 是已锁定 Coordinator。依赖缺失或跨 Run、Execution 状态改变、Contract 非法和 history 失败都不产生 Task。MySQL 行锁只保护短 dispatch 事务；不声称提供 Worker lease。

## 取舍

不调用通用 `create_task` 再做 ownership 检查，因为会产生检查与写入之间的竞态；不把 PENDING Task 自动置 RUNNING，因为 Worker ownership 属于后续 Change；不做批量 API，保持一个 request 一个 Task 的审计边界。
