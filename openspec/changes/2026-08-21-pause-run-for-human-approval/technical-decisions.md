# 技术选型

- 直接复用现有 Agent Run 表和 transition history，不新增 checkpoint 表：`WAITING_FOR_APPROVAL` 本身已经是生效 Contract 状态，本 Change 只补缺失的协调入口。
- 不调用独立 `AgentRunLifecycleService.transition_run`：该方法自行开启连接/事务，无法与 Approval 原子提交；本 Change在 Human Approval 已持有的连接上复用相同状态规则并执行 SQL。
- transition request ID 从 Approval ID 确定性派生：让 crash/replay 能验证同一事实，不依赖随机 ID 或调用方输入。
- 不把 Java Approval 状态复制进本 Change：Agent 侧 PENDING fact 是暂停依据；Java 决策同步和恢复属于后续 saga Change。
