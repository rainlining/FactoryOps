# Change 学习计划：2026-08-16-define-agent-task-contract

- `learning_level`: `deep`
- `pattern_stage`: `first-deep`
- `gate_status`: `completed-externally`

## 学习目标

- 能解释 Run、Task、Execution 的所有权和 retry 边界。
- 能定位 dispatch key、type/role、自依赖、终态和 revision 规则。
- 能依据错误 code/path 调试非法 Task。

## Owner 修改

- 任务：为 Task failure message 调整一个约定的长度边界，同步 Schema、测试和 README。
- 验收：边界值测试和全部 Task/Contract tests 通过。
- 安全：不改变 key、状态、role/type 或 retry 语义。

Review 会话记录（2026-08-17）：项目所有者明确要求由 Codex 代做。Codex 已将 Task `failure.message` 上限从 500 调整为 600，并同步 Schema、600/601 边界测试和 README。由于不是项目所有者亲自完成，本项不能计为 Owner 亲自修改，Deep Learning Gate 不自动通过。

## Failure/Debug Exercise

- 注入：修改合法 Task 的 `task_request_id`，保留旧 `task_key`。
- 预期：`task_key_mismatch`，path 为 `$.identity.task_key`；重算后通过。
- 观察：pytest、错误 code/path、新旧 key。
- 常见错误：只校验 key 格式、以 role 幂等、retry 新建 Task。
- 清理：还原临时 fixture，不提交实验修改。

Review 会话结果（2026-08-17）：已在内存中修改合法 Task 的 `task_request_id` 并保留旧 key，实际得到 `task_key_mismatch`、path `$.identity.task_key`；随后调用 `compute_task_key` 重算并验证通过。未修改或提交 fixture。

## Learning Gate

- [ ] 解释设计与取舍。
- [x] 定位成功和失败调用链。
- [ ] 完成 Owner 修改和故障实验。
- [ ] 指出 Contract 与后续数据库并发保护边界。
- [ ] review 最终 diff 并明确接受。

实现会话只准备材料；Review/Learning 会话完成上述任务。不得并发修改同一 worktree。
