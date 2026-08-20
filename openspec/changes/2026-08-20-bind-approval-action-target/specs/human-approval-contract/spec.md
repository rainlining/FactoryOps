# Human Approval Contract 增量规格

## Requirement: v1.1 binds immutable incident provenance

Human Approval v1.1 identity 必须包含 `incident_id`。validator 必须验证 Approval run 等于 Risk Decision run、source Run identity 等于该 run，且 Approval incident 等于 source Run provenance incident。

### Scenario: incident substitution

合法 Risk/Run 对应的 Approval 替换为另一合法 incident ID 时必须拒绝。

## Requirement: version compatibility

v1.0 legacy canonical/read/replay 必须继续工作；v1.1 canonical/relation 必须包含 incident。不同 Contract version 不得被分类为 identical 或 next revision。

## Requirement: executable approval intake

Java internal create 必须拒绝新 v1.0 PENDING，只接受含 incident binding 的 v1.1；既有 v1.0 current/history 仍可读取。
