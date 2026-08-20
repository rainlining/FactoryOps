# 技术选型

- 复用 `BatchApplicationService.hold`：嵌套的 Spring `TransactionTemplate` 使用同一事务管理器并加入外层事务，保留成熟的 evidence 与状态规则。
- action receipt 存 MySQL，不用 Kafka：本 Change 的副作用和审计必须原子提交。
- endpoint 无 request body：消除 Batch/Line target substitution 面。
- V1 只支持 HOLD_BATCH：现有 Batch 聚合已冻结；STOP_LINE/REJECT_ITEM 需要独立业务模型，不能在本 Change 静默发明。
