# 技术选型

- current + append-only history：查询方便且完整保留审批审计轨迹。
- MySQL advisory admission lock + row lock + revision CAS：处理缺失 PK 并发 insert、identity split 和终态竞争。
- 保存事务完整锁定 Risk/Fusion provenance；不把 Contract 层信任升级成数据库事实信任。
- 不引入 Redis、Kafka 或新基础设施。
