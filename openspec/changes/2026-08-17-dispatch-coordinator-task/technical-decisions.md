# 技术选型：Coordinator Task Dispatch

| 主题 | 选择 | 理由 |
|---|---|---|
| 并发 | Execution/Run `FOR UPDATE` | 确保 owner 状态和父 Run 在同一短事务内稳定 |
| 幂等 | 既有 `task_request_id` 唯一键 + payload 摘要 | 复用 Task Contract 语义，支持 at-least-once 重放 |
| 状态 | 只创建 PENDING | dispatch 不等于 Worker claim |
| 依赖 | 既有 junction table 与同 Run FK | 保持 Task persistence 的事实来源 |
