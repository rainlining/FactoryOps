# Change 设计：2026-08-16-define-agent-task-contract

## 边界与所有权

```text
Workflow Run
└── Coordinator Execution
    ├── Quality Task
    │   ├── Quality Execution attempt 1
    │   └── Quality Execution attempt 2
    └── Risk Task (depends on Quality Task)
```

- Run 拥有 Workflow；Coordinator Execution 创建 Task；Task 拥有稳定工作要求；Execution 拥有一次 attempt。
- Task 只引用 Context、Evidence、依赖 Task、当前/终态 Execution，不复制完整对象。

## 数据流

1. Coordinator 生成稳定 `task_request_id` 和不可变输入。
2. helper 以 version、Run 和 request ID 计算 `task_key`。
3. Validator 执行版本、严格 Schema、key、type/role、自依赖、引用和时间检查。
4. 后续 Repository 以 `(run_id, task_request_id)`/key 唯一约束分类重投。
5. Task 从 PENDING 进入 RUNNING；Execution retry 仍属于同一 Task。
6. 最终成功/失败引用对应 Execution；依赖失败可进入 SKIPPED。

## 状态与不变量

- 状态边：`PENDING→RUNNING|CANCELLED|SKIPPED`；`RUNNING→SUCCEEDED|FAILED|CANCELLED`；终态不可离开。
- 本 Change 无事务；后续 snapshot/history 必须同事务并使用 revision 乐观锁。
- identity、creator、type、role 和 input 在 revision 演进中不可变。
- key 必须匹配 version/Run/request；依赖和 Evidence 不重复；不得自依赖。
- `created_at`、`started_at`、`ended_at` 不晚于 `updated_at`；`started_at` 写入后不变。
- result/failure 与状态严格互斥。

## 失败与测试

- 不支持版本、未知字段、ground truth：提前拒绝。
- key、role/type、自依赖、重复引用、时间错误：稳定 code/path 拒绝。
- immutable 改写、revision 跳跃、非法状态边：分类 conflicting。
- Contract Test 覆盖 Schema、fixtures、semantic validator、canonical key/form 和 relation。
- 集成测试 N/A：无持久化/传输边界；仍运行全部 Agent/Java 回归。

## 方案取舍

- request ID 而非 role 作为 dispatch 幂等：同角色可拥有多个 Task。
- retry 复用 Task、新建 Execution：工作要求不变但每次执行事实独立。
- 固定 type/role 映射：v1 拒绝动态 Agent，避免 Coordinator 越界调度。
- 依赖使用 Task ID 列表而非内嵌 DAG：保持 Contract 小且避免循环对象。
- 不同时做数据库/Worker：避免一次 Change 发明 Contract、事务和并发 ownership。

## 连续 Apply

1. OpenSpec 与 RED tests。
2. Schema、fixtures、Validator 与局部验证。
3. 全量回归、独立审查和 Important 修复。
4. verification/handoff、提交并推送 stacked branch。
