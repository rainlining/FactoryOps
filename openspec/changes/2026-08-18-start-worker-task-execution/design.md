# Change 设计：启动 Worker Task Execution

入口为 `WorkerTaskExecutionService.start`。事务锁顺序固定为 start request → Task → lease；验证 Task=PENDING、revision=0、lease ownership/expiry 和直接依赖全 SUCCEEDED。随后写入 RUNNING Execution snapshot、PENDING revision 0 与 RUNNING revision 1 history，再更新 Task 和写 Task history，最后保存 request fingerprint。

Execution 直接以 RUNNING snapshot 落库，但完整保留 PENDING/RUNNING 两条 append-only history；这避免调用现有两个 Service 产生跨事务部分提交。Task 行锁串行化同一 Task 的启动，lease token 提供 owner fencing。请求表只保存 SHA-256 命令指纹与结果 ID，不保存 lease secret 明文。

失败路径包括无效/过期 lease、Task 非 PENDING、依赖未满足、条件更新失败、唯一键或 history 失败；事务统一回滚。测试使用真实 MySQL 覆盖成功、重放、lease 失败、依赖失败和注入回滚。
