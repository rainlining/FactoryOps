# 技术选型：启动 Coordinator Execution

| 主题 | 选择 | 理由 |
|---|---|---|
| 原子性 | MySQL InnoDB 单事务 | Run 与 Execution 在同库且已有 FK |
| 互斥 | Run `SELECT ... FOR UPDATE` | 启动临界区短，无需分布式锁 |
| 幂等恢复 | start receipt + payload SHA-256 | 覆盖提交成功但响应丢失 |
| Contract | 复用 Run/Execution Validator | 避免编排层复制结构语义 |
| provenance | Run 冻结字段复制，prompt 显式输入 | Coordinator prompt 可比 Run prompt set 更具体 |

receipt 是 use-case 请求日志，不取代 Run/Execution history。后续 Worker lease 必须独立定义 owner、expiry、renewal 和 fencing token。
