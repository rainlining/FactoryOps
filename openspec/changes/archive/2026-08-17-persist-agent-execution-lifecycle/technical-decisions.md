# 技术选型：Execution 生命周期持久化

| 主题 | 选择 | 理由 |
|---|---|---|
| 数据库 | MySQL 8.4 + SQLAlchemy Core | 延续现有 Agent persistence |
| 模型 | snapshot + append-only history | 恢复当前状态并保留审计 |
| 幂等 | execution_key / transition_request_id 唯一键 | 抵御 at-least-once 与竞态 |
| 并发 | status/revision 条件 UPDATE | 无长事务或分布式锁 |
| 引用数组 | JSON + Contract Validator | Artifact/Context/Decision 尚无本地表 |
| 父关系 | Run/Task/Execution 双向 FK，RESTRICT | 将阶段性逻辑引用升级为数据库事实 |

004 是严格 migration：孤立 Execution 引用不自动修复。上线前应查询 Run/Task 非空 Execution 列并准备对应 snapshot/backfill；当前测试数据库在 migration 前为空。
