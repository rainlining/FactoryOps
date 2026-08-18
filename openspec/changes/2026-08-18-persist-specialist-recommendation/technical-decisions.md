# 技术选型

- canonical payload 使用 LONGTEXT + JSON_VALID，而非 MySQL JSON：避免数据库重排/数值归一化改变原 canonical bytes。
- 同时保存 typed identity/action 列：支持 FK、唯一约束和后续 Fusion 查询；读取时与 payload 双向核对。
- 首次写入要求 current RUNNING pair；已有事实重放不再要求父对象仍 RUNNING，支持 Completion 后恢复。
- 不把 Recommendation 保存与 Worker Completion 合并：模型输出事实可以先提交并幂等恢复，Completion 后续引用 Artifact/Decision 边界。
