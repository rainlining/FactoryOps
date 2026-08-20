# Design

## 数据流与事务

入口仍是 `HumanApprovalService.save(PENDING approval)`。服务沿既有锁序锁定 Fusion provenance、Risk Decision、来源 Run，再锁 Approval identity。只有 Risk/Approval Contract 全部验证后，才在同一事务中：

1. 插入 Approval current/history；
2. 对已锁定 Run 执行 `RUNNING/revision N → WAITING_FOR_APPROVAL/revision N+1`；
3. 写入一条以 Approval ID 派生 request ID 的 Run transition history；
4. 一次提交。

确定性 request ID 为 `TRQ-` 加 `SHA256("approval-wait-v1\n<approval_id>")` 大写十六进制的前 32 位，以满足既有 transition request ID 长度。reason code 固定 `HUMAN_APPROVAL_REQUIRED`，actor 为 `COORDINATOR / human-approval-service`，reason message 绑定 approval key。现有 provenance-first 锁序不变，Run 在 Approval 前锁定。

## 幂等与失败

- 首次 PENDING Approval 只接受来源 Run 为 RUNNING；Approval insert 或 Run transition 任一失败，事务整体回滚。
- 相同 Approval 重放要求 Approval canonical identical，并要求确定性 wait transition 与从该 revision 到 Run current 的后续 transition 形成连续合法历史链。Run 尚未恢复时，current 的 status/reason/updated_at 必须与 wait transition 一致；合法恢复后不要求 Run 永久停在 WAITING。
- 相同 Approval identity 的不同 payload 仍为 duplicate-conflicting，不改变 Run。
- Run 已终态、SUSPENDED 或由无关 transition 进入 WAITING 均 fail closed，不补写或覆盖历史。
- terminal Approval revision 的保存不负责恢复 Run；批准后的恢复与业务动作属于下一个 Change。

## 测试

真实 MySQL 覆盖 applied、identical replay、合法恢复后历史可读、conflicting replay、Approval insert/transition rollback、错误 Run 状态、Run summary/transition corruption，以及并发相同创建只产生一条 Approval 和一条 wait transition；随后执行 Agent 全量、Contract、Java、Ruff 与 diff/dataset 检查。
