# Design

## 数据流

入口为 `ApprovedActionResumeService.resume(terminal_approval)`：

1. 在任何写入前先做无副作用 scope precheck，只接受 revision 2 APPROVED v1.1 HOLD_BATCH；再用既有 `HumanApprovalService.save` 保存 terminal fact，相同 terminal replay 必须 identical。
2. 要求 v1.1、HOLD_BATCH、来源 Run 的确定性 wait history 完整。
3. 通过 `BusinessActionClient` 调用 `POST /internal/api/v1/approvals/{approval_key}/execute`，只发送 service token 和空 JSON，不传 target。
4. 严格校验回执 approval key、action、incident、status 与 Approval 一致，并要求 batch ID、executed_at、replayed 类型有效。
5. Agent 事务沿既有锁序锁定 Fusion 完整 provenance、Risk Decision、Run、Approval current/history 及完整 wait-to-current transition chain；持有这些 fence 期间调用有限 timeout 的 Java API，随后以从 Approval ID 派生的 transition ID/request ID原子执行 `WAITING_FOR_APPROVAL → RUNNING`。
6. 再读取 Approval，验证 wait→resume 历史链和 Run current summary。

## Saga 与失败窗口

Java DB 与 Agent DB 不存在分布式事务，也不引入 2PC。顺序固定为：terminal Approval 本地落库 → Java 幂等 action → Agent Run resume。

- Java 调用前失败：Approval 可相同重放，Run 仍 WAITING。
- Java 未执行/返回失败：Run 保持 WAITING；重试 terminal Approval identical 后再次调用。
- Java 已执行、响应丢失或 Agent resume 失败：重试 Java 返回 replay，再以确定性 transition request ID 完成或分类 identical。
- 回执字段不匹配：fail closed，Run 不恢复。
- Run 被无关 transition 抢先改变：返回 concurrency/integrity failure，不覆盖状态。
- 从 Java 调用开始到 Run resume commit 持有 Run row fence，阻止审批已验证后被并发 cancel/suspend 抢占；外调 timeout 上限 30 秒，避免无界持锁。

## HTTP 边界

生产 adapter 使用 Python 标准库同步 HTTP，只接受无 userinfo/path/query/fragment 的 `http/https` origin，拒绝 redirect，限制响应体为 1 MiB，并配置 service token 和有限 timeout；非 2xx、malformed JSON、网络/timeout 都转为稳定领域异常，不自动循环重试。service 层只依赖 Protocol，真实 MySQL saga 测试使用 recording fake；Java endpoint 和 Agent HTTP adapter 都由共享 `approved_action_receipt/v1.0.0` Schema 验证。

## 测试

真实 MySQL 覆盖 applied、Java replay、terminal duplicate、Java failure、receipt mismatch、Java 成功后 transition failure再恢复、并发相同 resume、Approval/history corruption 和外调期间 provenance update 被阻塞。HTTP adapter 覆盖 header/path/body、共享 Schema、2xx decode、非 2xx/malformed/timeout/redirect 分类。然后执行 Agent/Contract/Java 全量、Ruff、diff/dataset 检查。
