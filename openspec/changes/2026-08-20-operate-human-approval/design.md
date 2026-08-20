# 设计：Human Approval Application/API

Business Service 通过受 service token 保护的 internal endpoint 接收完整 Human Approval v1.0.0 PENDING Contract，以共享 JSON Schema 和确定性语义校验拒绝未知字段、错误派生 identity 及非法时间窗口。Risk/Fusion 来源真实性由已验证该来源的 Agent Workflow 和 service token 信任边界保证；Java 不跨服务直读 Agent 数据库。Java 数据使用独立 `business_approvals` / `business_approval_history`，避免与 Agent Runtime 的 workflow fact 表混淆。

创建事务按 approval key 对 current row 串行化；相同 canonical PENDING 为 replay，不同 payload 或 key/ID split 为 conflict。决定事务 `SELECT ... FOR UPDATE` 锁 current，只允许 PENDING → APPROVED/REJECTED；相同 actor/outcome/reason/comment 的终态重放返回 replay，任何其他终态命令冲突。current 与 revision history 同事务更新。

Controller 只接受 `X-FactoryOps-Actor-Id`。`ApprovalAuthorizer` 从服务端配置 allowlist 解析 actor；客户端不能声明自身角色。v1 只区分“已授权审批者/未授权”，不发明动作级岗位策略。默认 allowlist 为空，生产样式配置缺失时 fail closed；本地 demo 可显式配置 actor。

本 Change 不发布完成事件，因为现有通用 outbox 表仍带 Quality Incident 专用外键。移除该约束或新增多 aggregate outbox 属于后续 Workflow/Event Change，不能在审批 API 中静默弱化一致性。

失败路径：Contract/command 错误为 422，未授权为 403，不存在为 404，identity/terminal conflict 为 409；事务异常不得留下半 history。过期 PENDING 不接受人工决定，自动 EXPIRED 由后续定时编排负责，本 API 不在读取时偷偷写状态。
