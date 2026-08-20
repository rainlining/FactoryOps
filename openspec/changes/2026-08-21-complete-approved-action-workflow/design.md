# Design

## 编排与事务

入口 `ApprovedWorkflowCompletionService.complete(terminal_approval)` 复用 `ApprovedActionResumeService.resume`，但通过事务内 `before_business_hook` 在 Java 调用前锁定并验证 Coordinator、全部 Task/归属 Execution 及 Run 完整 history；fence 覆盖 Java HOLD 与 Run resume。Java receipt 是业务副作用幂等锚点，Run resume transition 是工作流恢复锚点。随后在新的 Agent MySQL 事务中按既有顺序重新锁定并验证全部 readiness，再锁两个确定性 completion transition identity。

readiness 必须同时满足：Approval 为 v1.1 revision 2 APPROVED HOLD_BATCH；Run 为 `RUNNING` 且当前原因是前一 Change 的 `APPROVED_ACTION_EXECUTED`；Coordinator 属于同 Run、role=coordinator、status=RUNNING；Run 至少有两个 Task且每个 Task 与其 completion Execution 都为 SUCCEEDED。现有 dispatch/completion 尚未增量维护 Run progress counters，本事务以已锁定 Task/Execution 实际集合为权威，在终态 snapshot 校准 Task 与 Execution counters；不在本 Change 重写历史 Task 服务。

同一事务以同一个数据库时间：

1. Coordinator Execution `RUNNING → SUCCEEDED`，result 绑定 Fusion artifact、Risk Decision key 与 Approval evidence；既有 Execution Contract 的 `decision_id` 仅接受 `DEC-*`，Risk 使用 `RSK-*`，因此该字段保持 null，不伪造 ID；
2. Run `RUNNING → SUCCEEDED`；
3. 插入两条从 Approval ID 确定派生的 transition facts。

任一写入、history 或 readiness 失败全部回滚。重放必须同时命中并完整验证两条 transition 和两个 current snapshot；只命中一侧、identity split 或字段漂移必须 fail closed。

## 并发与失败

- concurrent identical：Run row fence 串行化，只允许 `APPLIED + DUPLICATE_IDENTICAL`。
- completion admission 使用独立 `NullPool` 连接，不占用业务连接池；等待按 35 秒分片并受默认 120 秒总 deadline 约束。分片超时继续等待，deadline 超限分类为基础设施完整性失败而非业务拒绝。第二调用取得同一 Approval admission 后读取确定性 completion facts；外部 owner 异常不释放时也能有界退出。
- concurrent cancel/failure：Run CAS 单赢家，完成不能覆盖已改变状态。
- Java 已执行但 completion rollback：重试先得到 Java replay，再完成 Agent 双聚合。
- readiness 未满足：不改变 Coordinator/Run，不伪造 Worker 成功。

## 测试

真实 MySQL 覆盖成功、重放、跨多个 admission 等待分片的并发 identical、业务池容量并发、外部 owner deadline、Task 未完成、Coordinator 非 RUNNING、Coordinator/Run/transition corruption、单边写入注入失败整单回滚与 completion/cancel 竞争；再运行 Agent、Contract、Java 全量、Ruff、diff 和 dataset 检查。
