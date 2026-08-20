# Human Approval Persistence 增量规格

## Requirement: persisted incident matches Run

Agent 保存 v1.1 Approval 时必须在原事务内锁定并重验 source Run；`incident_id` typed column、canonical payload 和 Run provenance 必须一致。任一错误或并发漂移必须回滚且不新增 current/history。

### Scenario: Run incident drift

保存期间 Run incident 被并发修改时，修改不得在 Approval commit 前越过锁；最终若 provenance 不匹配则 Approval 保存拒绝。
