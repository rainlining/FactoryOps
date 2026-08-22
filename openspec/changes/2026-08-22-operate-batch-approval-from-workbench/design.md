# Design：从工作台处理批次审批

## 边界

- `Approval store` 在共享 SQLite 中保存审批当前态与 append-only history。
- `Approval service` 以队列项为所有权边界，锁定 `WAITING_FOR_APPROVAL` 项并执行确定性状态迁移。
- `Approval API` 只接受枚举决定、非空审批人和有限长度意见。
- 前端待审批区负责证据展示、二次确认和提交，不推导业务状态。

## 状态与动作

```text
WAITING_FOR_APPROVAL
  ├─ APPROVE  → APPROVED_ACTION_PENDING
  ├─ REJECT   → APPROVAL_REJECTED
  ├─ RECHECK  → RECHECK_REQUESTED + 新 QUEUED revision
  └─ ESCALATE → ESCALATED
```

`APPROVE` 表示人已批准 Risk 建议，不表示物理动作已执行；页面必须显示“待业务系统执行”。`RECHECK` 使用原 Artifact 创建派生队列项，旧 Run 和审批记录不变。

## 数据模型

- `batch_approvals`：approval_id、item_id、run_id、status、decision、actor、comment、recommended_action、revision、timestamps。
- `batch_approval_history`：每次 revision 的不可变 JSON 快照。
- 每个队列项最多一个审批身份；同一 command_id 重放返回原结果，不同决定在终态后返回冲突。

## 失败路径

- 非待审批项、缺少 Run、非法决定或空审批人：拒绝且不写库。
- 已终态审批收到不同命令：409，不改变事实。
- 复检派生项创建与审批终态在同一 SQLite 事务完成。
- 服务重启后从 SQLite 恢复，不依赖浏览器内存。

## 测试

- 服务层：四种动作、幂等、冲突、非法状态、复检原子性、历史不可变。
- HTTP：列表、详情、提交与错误分类。
- 前端 Contract 与浏览器：待审批卡片、证据、二次确认、结果反馈和刷新恢复。
