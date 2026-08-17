# 技术选型：Task Lease

| 主题 | 选择 | 理由 |
|---|---|---|
| 存储 | MySQL 独立 lease 表 | 当前 Task 与 Agent Service 同库 |
| token | UUID + 随机字节 | 防止 owner ID 猜测和陈旧释放 |
| 过期 | UTC 时间比较 | 允许接管且无需后台清理 |
| 生命周期 | 不改 Task/Execution | claim 与执行事实分离 |
