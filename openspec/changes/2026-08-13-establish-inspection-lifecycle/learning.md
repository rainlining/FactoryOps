# Change 学习计划：2026-08-13-establish-inspection-lifecycle

## 学习元数据

- `learning_level`: `deep`
- `pattern_stage`: `first-deep`
- `first_deep_reference`: `2026-08-11-accept-vision-inspection-result`（复用组件模式，但新增聚合、跨表事务与并发语义）
- `gate_status`: `not-started`

## 完成后应具备的能力

- 区分 Inspection 聚合不变量、跨表事务不变量和数据库约束。
- 沿创建、查询、首次完成、并发完成调用链定位真实代码。
- 解释为什么条件更新而非 Java 预判断保护首次完成时间。
- 根据数据库行数、时间和测试证据调试原子性与并发错误。

## 编码前讲解清单

- [x] 业务问题与工程问题
- [x] 组件边界与所有权
- [x] 数据流和状态迁移
- [x] 事务、并发和关键不变量
- [x] 失败、重试、幂等和恢复路径
- [x] 测试与可观测性策略
- [x] 替代方案与取舍

## 真实 Code Walkthrough 路线

实现后填写创建/查询 Controller、应用编排、Inspection Domain、事务、Repository/Flyway、错误恢复和对应测试的真实文件与符号。

## 项目所有者亲自修改任务

- 任务：为查询响应增加 `result_count`，用只读聚合查询返回已保存 Result 数量，并覆盖 PENDING、首次完成和多 Result。
- 理解要求：必须理解一对多关系与查询模型，不能靠机械改名。
- 验收：三个场景测试及全套验证通过。
- 安全边界：不修改状态迁移、写事务、唯一键或外键。

## Failure/Debug Exercise

- 注入故障：把完成 SQL 从 `WHERE status='PENDING'` 改成无条件更新。
- 操作：固定两个并发 Result 使用不同 Clock 时间并运行并发测试。
- 预期：测试发现 `completed_at` 被后到事务覆盖。
- 证据：响应、数据库最终时间、SQL 更新行数和失败断言。
- 常见错误：只在 Java 判断状态，误以为读取后状态不会变化。
- 复位：恢复条件更新并运行全套测试。
- 应能回答：为什么 Java 预判断不能替代条件 SQL；为什么第二份 Result 可保存但不能再次完成。

## Learning Gate

- [ ] 能解释真实设计和关键取舍。
- [ ] 能沿成功调用链定位核心代码。
- [ ] 能定位并解释至少一条失败路径。
- [ ] 已亲自完成约定的小修改。
- [ ] 已完成故障实验并根据证据判断结果。
- [ ] 能指出事务、幂等和恢复逻辑的实际执行位置。
- [ ] 已 review 最终 diff 并明确接受。

## 会话边界

实现会话连续完成实现与技术验证并停在 handoff；独立 Review/Learning 会话完成 Walkthrough、owner 修改、故障实验和最终验收。两个会话不得同时修改本 worktree。
