# 学习计划

- `learning_level`: `deep`
- `gate_status`: `not-started`

Review 需解释旧 Execution 终态、新 Execution 创建、Task attempt replacement 和 lease 保留为何必须同事务。Owner 修改：在安全错误 allowlist 中增加一个明确的测试错误码并补拒绝/接受测试。Failure exercise：注入新 Execution RUNNING history 失败，观察旧 Execution 与 Task 均仍 RUNNING、没有 retry fact。Learning Gate 在独立 Review/Learning 会话完成。
