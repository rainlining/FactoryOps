# Learning：扫描 FactoryOps 批次队列

- `learning_level`: `delegated`
- `status`: `deferred-by-owner`

## 学习目标

- 理解根目录、批次、队列项和 Run 的身份区别。
- 理解为什么质检通过不等于业务 Batch 自动 `RELEASED`。
- 理解确定性路由器与 LLM 建议之间的权限边界。
- 理解暂停、取消、失败恢复和显式重试的不同语义。

## Walkthrough 路线

Review 会话应从前端根目录扫描入口开始，依次查看队列 API、SQLite 领取事务、现有 Run 创建、终态路由、重启恢复和对应测试。

## 所有者修改与故障实验

本 Change 为 delegated，所有者修改和故障实验不作为归档门禁。建议实验：让第二个批次的 Agent 调用失败，观察第一批与第三批不受影响、失败批次保留证据且仅在显式重试后创建派生 Run。
