# Change 设计：启动 Worker Task Execution

入口为 `WorkerTaskExecutionService.start`。锁顺序固定为 request-key named advisory lock → start request → Task → lease；验证 Task=PENDING、revision=0、lease ownership/expiry 和直接依赖全 SUCCEEDED。随后写入 RUNNING Execution snapshot、PENDING revision 0 与 RUNNING revision 1 history，再更新 Task 和写 Task history，最后保存 request fingerprint。

Execution 直接以 RUNNING snapshot 落库，但完整保留 PENDING/RUNNING 两条 append-only history；这避免调用现有两个 Service 产生跨事务部分提交。Task 行锁串行化同一 Task 的启动，lease token 提供 owner fencing。请求表只保存 SHA-256 命令指纹与结果 ID，不保存 lease secret 明文。

MySQL `GET_LOCK` 名称使用 request ID 的 SHA-256 派生值，避免明文和 64 字节限制；锁绑定当前数据库 connection，在业务事务外取得，并在 `finally` 显式 `RELEASE_LOCK`。它只串行化相同 request key，不扩大 Task ownership，也不替代 Task/lease 行锁。这样不同 Task 的同 request 不会在主键 INSERT 处暴露 duplicate key/deadlock，而会在前一个事务完成后重读 request fact 并分类。

失败路径包括 admission lock timeout、无效/过期 lease、Task 非 PENDING、依赖未满足、条件更新失败或 history 失败；事务统一回滚，advisory lock 始终释放。测试使用真实 MySQL 覆盖成功、顺序/并发重放、跨 Task request 冲突、lease 失败、依赖失败和注入回滚。
