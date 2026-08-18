# 学习计划

- `learning_level`: `deep`
- `gate_status`: `not-started`

Review 需沿 `start → Task/lease locks → dependency check → Execution histories → Task transition → request fact` 解释事务与 fencing。Owner 修改：把测试中的合法 `runtime-v1` 改为另一个非空版本并确认该 provenance 原样持久化。Failure exercise：注入第二条 Execution history 失败，观察 Task 保持 PENDING、Execution/request 均不存在。Learning Gate 在 Review/Learning 会话完成，本实现会话不得代做或归档。
