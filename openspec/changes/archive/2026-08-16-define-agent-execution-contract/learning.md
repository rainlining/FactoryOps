# Change 学习计划：2026-08-16-define-agent-execution-contract

## 学习元数据

- `learning_level`: `deep`
- `pattern_stage`: `first-deep`
- `first_deep_reference`: `N/A`
- `gate_status`: `completed-externally`

## 完成后应具备的能力

- 能解释 Run、Execution、Task 三种所有权以及为何 retry 创建新 attempt。
- 能从 fixture 沿 Schema、Validator、key 校验和 relation classifier 定位成功/失败路径。
- 能修改一个真实 Contract 约束并同步测试与文档。
- 能根据错误码和 JSON path 判断是结构错误、身份错误还是 revision 冲突。

## 编码前讲解清单

- [x] 业务问题与工程问题
- [x] 组件边界与所有权
- [x] 数据流和状态迁移
- [x] 事务、并发和关键不变量
- [x] 失败、重试、幂等和恢复路径
- [x] 测试与可观测性策略
- [x] 替代方案与取舍

## 真实 Code Walkthrough 路线

实现后由 handoff 填写真实文件与符号。

## 项目所有者亲自修改任务

- 任务：在 Review 会话把 failure message 的最大长度从当前值调整为约定的新值，并同步 Schema、fixture/test 与 README 边界。
- 为什么需要理解：必须找到嵌套 failure Schema、确认错误 path，并避免误改 status reason 或引用长度。
- 验收方法：新增边界值测试，运行 Agent Execution Contract tests 和全部 Contract tests。
- 安全边界：不改变 failure recoverability、生命周期、幂等 key 或生产安全控制。

Review 会话记录（2026-08-17）：项目所有者明确要求由 Codex 代做。Codex 已将 `failure.message` 上限从 500 调整为 600，并同步 Schema、600/601 边界测试和 README。由于不是项目所有者亲自完成，本项不能计为 Owner 亲自修改，Deep Learning Gate 不自动通过。

## Failure/Debug Exercise

- 注入故障：把合法 Specialist fixture 的 `attempt` 或 `task_id` 改掉，但保留旧 `execution_key`。
- 操作步骤：运行单 fixture Validator，观察错误；用公开 key helper 重新计算后再次验证。
- 预期行为：首次得到 `execution_key_mismatch` 和 `$.identity.execution_key`；修复后通过。
- 观察证据：pytest 输出、错误码、JSON path 和新旧 key。
- 常见错误行为：只校验 key 格式、使用自由 UUID、retry 改写旧 Execution 或摘要遗漏 role/attempt。
- 清理/复位：还原临时 fixture；不得提交调试变更。
- 完成后应能回答：为什么 `execution_id` 和 `execution_key` 都需要；Task 为什么进入 key；retry 为什么必须新建 attempt。

Review 会话结果（2026-08-17）：已在内存中把合法 Quality Execution 的 `attempt` 从 1 改为 2并保留旧 key，实际得到 `execution_key_mismatch`、path `$.identity.execution_key`；随后调用 `compute_execution_key` 重算，验证通过。未修改或提交 fixture。

## Learning Gate

- [ ] 能解释真实设计和关键取舍。
- [x] 能沿成功调用链定位核心代码。
- [x] 能定位并解释至少一条失败路径。
- [ ] 已亲自完成约定的小修改。
- [x] 已完成故障实验并根据证据判断结果。
- [ ] 能指出幂等与并发保护在 Contract 和后续持久化层各自的边界。
- [ ] 已 review 最终 diff 并明确接受。

## 会话边界

实现会话只准备真实路线、任务和实验；Review/Learning 会话完成 Owner 工作。两个会话不得并发修改同一 worktree。
