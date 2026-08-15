# Learning Plan：2026-08-15-define-agent-run-contract

## 元数据

- `learning_level`: `deep`
- `status`: `completed`

## 学习目标

项目所有者最终能够：

1. 区分 Workflow Run、Agent Execution、Task 和 Checkpoint。
2. 解释 `run_id` 为什么不能同时承担 original/replay 的幂等键。
3. 沿真实 Fixture → Validator → Schema → 语义检查定位成功和失败路径。
4. 解释 original/replay 双引用血缘以及哪些规则必须访问数据库才能验证。
5. 指出 immutable identity/provenance 与 mutable lifecycle 的边界。
6. 解释 ground truth 为什么不能进入 Agent Run Contract。

## Code Walkthrough 路线

独立 Review 会话按以下顺序阅读：

1. `contracts/agent_run/README.md`：对象边界和字段所有权。
2. `contracts/agent_run/fixtures/valid/original-run.json`：original 实例。
3. `contracts/agent_run/fixtures/valid/replay-run.json`：replay 血缘实例。
4. `contracts/agent_run/v1.0.0/schema.json`：结构、严格字段和条件组合。
5. `contracts/agent_run/validator.py`：版本前置、Schema 路径和跨字段不变量。
6. `contracts/agent_run/tests/`：每条设计如何由自动化证据保护。

## 项目所有者亲自修改任务

在 Review 会话中为 `status_reason.code` 增加最小长度约束或更严格 pattern，并：

- 增加一个会因旧规则通过、因新规则失败的 invalid fixture；
- 运行目标测试证明约束生效；
- 解释该修改为何属于 Contract 收紧，以及发布时是否需要升级版本。

最终任务细节可根据实现 diff 缩小，但不得改成机械重命名。

## Failure/Debug Exercise

注入一份看似合法的 replay：让 `replayed_from_run_id` 等于自身 `run_id`。

- 预期：Schema 结构可能通过，但语义 Validator 以稳定错误码和 `$.identity.replayed_from_run_id` 拒绝。
- 观察：目标测试输出、错误码、JSON path，以及 relation classifier 在分类前拒绝输入。
- 常见错误：只检查字段存在，不检查自引用；或将非法输入错误分类为 distinct。
- 复位：恢复 fixture 中合法的直接来源 Run ID，重新运行测试。
- 完成后应能回答：为什么单条 Validator 可以发现自引用，却不能完全发现跨多条记录形成的 replay 环。

## Learning Gate

- [x] 能用自己的话解释真实设计和关键取舍。
- [x] 完成真实成功调用链 Walkthrough。
- [x] 定位并解释至少一条失败路径。
- [x] 完成项目所有者亲自修改任务并通过测试。
- [x] 完成 Failure/Debug Exercise 并根据证据判断行为。
- [x] 指出幂等、不可变性和跨记录校验将在哪里执行。
- [x] Review 最终 diff 并明确接受 Change。

## 完成证据

- Owner 修改提交：`0dfe007c48710810c2ed94ecd09a0c6d93d89b20`。
- 修改内容：把 `status_reason.code` 的最小长度从 1 收紧为 3，并增加 `short-status-reason-code.json` 失败 fixture。
- Failure/Debug Exercise 使用 replay 自引用场景；非法输入由语义 Validator 拒绝，relation classifier 不参与分类。
- 项目所有者在本轮确认进入最终 diff review，并授权无遗留问题后归档；最终独立审查发现的问题已修复并重新验证。
- v1.0.0 尚未合并或发布，Owner 的约束收紧属于首版发布前修正，不要求为此升级 major version。
