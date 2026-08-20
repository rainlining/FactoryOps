# Verification

状态：`review-handoff-ready`。

## TDD 与局部证据

- 初始 RED：模块缺失，测试 collection fail；首轮 GREEN 又实际暴露 Run counters 从未维护及 Execution Contract 不接受 `RSK-*` decision ID。
- 取舍：以锁定的 Task/Execution 集合作为 readiness 真值，在终态校准 Run counters；Risk 用 evidence ref 绑定，`decision_id` 保持 null，不伪造 `DEC-*`。
- 局部真实 MySQL：completion 单测 `6 passed in 19.85s`。
- 相关 Approval/resume/worker completion 联合：`43 passed in 80.90s`。
- 覆盖成功、相同重放、并发 identical、未完成 Task、双聚合中点失败回滚、transition identity split。

## 全量验证

- Agent（第二轮修复后）：`256 passed in 599.00s`。
- Contract（第二轮修复后）：`154 passed in 1.26s`。
- Java `mvn verify -q`：退出码 0；XML `21 reports / 85 tests / 0 failures / 0 errors / 0 skipped`。
- Ruff check/format、`git diff --check` 通过；`git status --short -- dataset` 无输出。

## 独立首审修复

首审为 0 Critical / 4 Important：业务副作用早于 readiness、Task/Execution 归属与 history 不完整、Run 早期 history 未验证、10 秒 admission 小于 30 秒业务 timeout。新增 RED 覆盖后修复为：

- resume transaction 的 pre-business hook 在 Java 调用前锁定/验证 Coordinator、Task、completion Execution 和 Run 全历史；实际 completion 事务再次验证。
- Task/Execution 强制同 task/run/role，并验证 Task/Execution current Contract 与 revision 0→current history。
- Run 强制验证 revision 0→current 完整合法 chain 与 tail/current。
- 首次复审仍有 2 Important：pre-business hook 未拒绝合法终态的 Coordinator/Run；固定 35 秒仍不能覆盖数据库等待、最长 Java HTTP 与两个事务的总耗时。
- 新增 Coordinator 已 `CANCELLED` 的 RED，要求 Java client 调用次数为 0；preflight 现强制 Coordinator identity/role/task/status，并按确定性 wait/resume transition 验证 Run 当前业务阶段。
- admission 改为 35 秒有界阻塞分片并在超时后继续等待；测试用 0.05 秒分片与 0.3 秒赢家稳定获得 `APPLIED + DUPLICATE_IDENTICAL`，证明跨多个分片不会泄漏 timeout 分类。
- 修复后 completion + resume 局部为 `21 passed in 62.01s`。
- 第二轮修复后 completion + resume 局部为 `22 passed in 84.58s`。
- 第三次复审仍有 1 Important：所有 admission waiter 长期占用业务 pool 且无限循环，可能让持锁赢家拿不到执行连接。
- 新增 pool-size=2/3 callers 的真实 MySQL RED，以及外部 owner 持锁的 deadline RED；admission 改用独立 `NullPool` 连接、默认 120 秒 deadline，超限为 infrastructure integrity failure。
- 第三轮修复后 completion + resume 局部为 `24 passed in 135.74s`。
- 最终复审 HEAD `1c0cdbb`：0 Critical / 0 Important；局部真实 MySQL 复审因只读环境无临时目录未能启动，采用本会话此前 `24 passed` 证据；worktree、dataset、diff check clean。
- 非阻塞 Minor：service 创建的独立 NullPool admission engine 当前没有显式 dispose 生命周期；NullPool 不保留连接，后续可在服务容器生命周期中统一复用/释放。
