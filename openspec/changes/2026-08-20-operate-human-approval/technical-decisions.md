# 技术选型

- Spring MVC + JdbcTemplate：复用现有 Java Business Backend，不引入新框架。
- JSON Schema 2020-12：直接复用 Human Approval v1.0.0 wire contract；Java 再执行跨字段时间/identity 语义。
- `business_approvals` 命名空间：与 Agent workflow persistence 分离，避免共享 MySQL 时表名冲突。
- server-side actor allowlist：满足本地 demo 的真实 fail-closed 权限边界，同时把 SSO/RBAC 明确留作非目标。
- current + immutable history + row lock：单事务确定终态赢家；不依赖进程内锁。
- 暂不发布事件：现有 outbox 的 aggregate FK 还不是多态边界，后续 Change 统一演进。
