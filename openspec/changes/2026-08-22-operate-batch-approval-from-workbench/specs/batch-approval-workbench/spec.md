# Batch Approval Workbench Specification

## ADDED Requirements

### Requirement: 待审批事项必须可理解

系统必须列出所有 `WAITING_FOR_APPROVAL` 批次，并展示批次身份、原始 Run、Risk 建议、风险级别、政策依据和批次结论。

#### Scenario: 用户打开待审批详情

- **Given** 一个批次等待人工审批
- **When** 用户查看该事项
- **Then** 页面显示触发审批的证据和建议动作
- **And** 不重新调用任何 Agent

### Requirement: 审批决定必须确定性持久化

系统必须支持 `APPROVE`、`REJECT`、`RECHECK`、`ESCALATE`，保存审批人和意见，并以 append-only history 保留每个版本。

#### Scenario: 批准高风险建议

- **When** 用户批准 Risk 建议
- **Then** 状态变为 `APPROVED_ACTION_PENDING`
- **And** 页面明确说明尚待业务系统执行
- **And** 不声称生产线已经停止

#### Scenario: 要求复检

- **When** 用户选择 `RECHECK`
- **Then** 原审批变为 `RECHECK_REQUESTED`
- **And** 创建引用原批次 Artifact 的新队列 revision
- **And** 原 Run 保持可回放

### Requirement: 审批命令必须幂等且失败关闭

相同 command_id 和相同内容必须返回相同事实；终态后不同命令必须冲突拒绝。非法状态、身份或决定不得产生部分写入。
