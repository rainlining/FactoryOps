# Change 学习计划

- `learning_level`: `standard`
- `pattern_stage`: `then-standard`
- `first_deep_reference`: `2026-08-15-persist-agent-run-lifecycle`
- `gate_status`: `not-started`

Review 应能解释 Run/Task/Execution 创建顺序、两个事务边界、attempt key、三类冲突与双向 FK；沿 Service → rules/Validator → Repository → MySQL 定位成功与失败链。Standard 不要求强制 Owner 修改或 Deep failure exercise，但应实际运行 stale revision/回滚测试并 review 最终 diff。
