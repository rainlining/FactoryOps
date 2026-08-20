# 技术选型

- Contract minor version `1.1.0`：不破坏 v1.0 历史 replay/read。
- `incident_id` 而非通用 target：当前 Run 根事实由 Quality Incident 触发，Java 可确定性解析 incident→batch；STOP_LINE 后续可由 batch→production line 解析。
- nullable migration + new-write required：避免伪造 legacy backfill。
- Agent 保存时锁 Run：Contract 结构信任必须升级为数据库 provenance 信任。
- Java 新建只收 v1.1、读取兼容 v1.0：阻止继续产生不可执行的新审批。
