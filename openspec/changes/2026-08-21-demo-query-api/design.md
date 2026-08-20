# Design

查询在单个只读事务中读取 Run 及其关联事实；MySQL 一致性快照负责本次读取，不声称持有写锁。按固定顺序返回 `run → coordinator → tasks → executions → fusion → risk → approval`，并验证完整 provenance 链。缺失关联返回 `null` 或空数组；跨 Run、identity split、非法 JSON 或关键字段不一致抛出完整性错误，不拼接部分快照。

响应只包含展示所需字段，不返回 raw prompt、token、模型上下文或 `payload_json` 原文。Business Receipt 位于 Java Business DB，不在本 Change 跨数据库读取，后续 adapter 才能补齐；服务不拥有写权限，调用方不能借查询推进状态。
