# 技术选型：Agent Task Contract v1.0.0

- `task_id`: `TSK-` + 32 位大写十六进制。
- `task_request_id`: `TQR-` + 32 位大写十六进制，由 Coordinator 稳定生成。
- `task_key`: `TAK-` + SHA-256(`v1\n<run_id>\n<task_request_id>`) 大写摘要。
- type/role 固定映射，不提供自由 metadata。
- input 保存 `context_snapshot_id`、`evidence_refs`、`dependency_task_ids`。
- lifecycle 使用 revision 当前快照；后续持久化 Change 保存 append-only history。
- success 保存 `successful_execution_id`；failure 保存 `failed_execution_id`、稳定 code/message 和 `recoverability`。
- `SKIPPED` 表示确定性地无需执行，区别于技术失败和人工取消。
- JSON Schema Draft 2020-12 负责结构，Python Validator 负责摘要、映射、自依赖、时间与跨快照关系。
