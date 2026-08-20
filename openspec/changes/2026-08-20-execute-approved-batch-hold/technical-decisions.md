# 技术选型

- 复用 `BatchApplicationService.hold`：嵌套的 Spring `TransactionTemplate` 使用同一事务管理器并加入外层事务，保留成熟的 evidence 与状态规则。
- action receipt 存 MySQL，不用 Kafka：本 Change 的副作用和审计必须原子提交。
- endpoint 无 request body：消除 Batch/Line target substitution 面。
- V1 只支持 HOLD_BATCH：现有 Batch 聚合已冻结；STOP_LINE/REJECT_ITEM 需要独立业务模型，不能在本 Change 静默发明。
- 采用 `MANUAL_QUALITY_HOLD` 而非 `QUALITY_ANOMALY`：Quality Incident 负责绑定目标与保留检测 provenance，Human Approval 是本次人工授权来源；执行层不把已有检测事实重新伪装为一次自动异常命令，也不重复解析 inspection/result evidence。
- receipt 同时以 Approval ID 与 Key 寻址并完整比对：单字段唯一约束不足以稳定识别 typed identity 分裂；OR-lock 让一侧仍正确的漂移稳定进入显式完整性拒绝，而不是由唯一键异常决胜。
