# Change 学习计划：2026-08-13-establish-quality-incident

## 学习元数据

- `learning_level`: `deep`
- `pattern_stage`: `first-deep-for-multi-fact-atomic-transaction`
- `first_deep_reference`: `2026-08-13-establish-inspection-lifecycle`（复用事务组件，新增三对象原子事实）
- `gate_status`: `not-started`

## 编码前必须理解

- Result、Inspection Completion、Incident 为什么必须在同一事务。
- Incident 为什么是业务问题单而不是模型输出副本。
- 派生 ID 与数据库唯一键分别保护什么。
- Java 证据验证与数据库外键为什么同时需要。
- Incident 创建为什么不等于 HOLD Batch。
- replay 如何返回原 Incident，以及为何不盲目自动 retry。

## 编码前讲解清单

- [x] 业务问题、对象区别和非目标
- [x] 组件边界与端到端数据流
- [x] 状态、事务、并发和不变量
- [x] 失败、重放、恢复与可观察证据
- [x] Schema、迁移和 HTTP Contract
- [x] 测试策略与替代方案

## 真实 Code Walkthrough 路线

实现后填写 Result HTTP 入口 → Validator → Intake 写事务 → Result/Inspection Repository → QualityIncidentService → ID 派生 → Incident Repository → 响应，以及 Incident GET 只读链。

## 项目所有者亲自修改任务

- 任务：为 Incident 查询响应增加派生字段 `result_origin_kind`。
- 实现边界：Query Service 在只读事务中按 `result_id` 查询不可变 Result；不得把字段复制到 Incident 表。
- 验收：至少覆盖两个 origin；不得修改写事务、Incident Schema 或 Result Contract。
- 学习目标：区分持久化所有权与查询组合。

## Failure/Debug Exercise

- 注入故障：让 Incident INSERT 触发数据库错误。
- 预期：HTTP 失败；Result=0；Incident=0；Inspection 保持 PENDING，`completed_at` 为空。
- 观察：三张表、HTTP 状态、事务异常和测试断言。
- 常见错误：在事务外或提交后创建 Incident，导致部分提交。
- 复位：移除故障约束/注入并重新运行原子回滚与完整测试。
- 完成后应能回答：最外层事务在哪里；异常如何传播；为什么重试相同 Result 安全。

## Learning Gate

- [ ] 能解释三对象原子事务和关键取舍。
- [ ] 能沿成功链定位真实代码。
- [ ] 能定位 Incident INSERT 失败路径。
- [ ] 已完成 `result_origin_kind` 修改。
- [ ] 已完成故障实验并依据数据库证据判断。
- [ ] 能指出事务、唯一键、外键、派生 ID 和 replay 的执行位置。
- [ ] 已 review 最终 diff 并明确接受。

## 会话边界

实现会话连续实现至 `review-handoff-ready`；独立 Review/Learning 会话完成 Walkthrough、owner 修改、故障实验与最终验收。两个会话不得同时修改本 Change/worktree。
