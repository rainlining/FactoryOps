# Change 学习计划：2026-08-13-establish-batch-lifecycle

## 学习元数据

- `learning_level`: `deep`
- `pattern_stage`: `first-deep-for-production-state-command`
- `first_deep_reference`: `2026-08-13-establish-inspection-lifecycle`（复用事务组件，新增状态命令、证据和锁语义）
- `gate_status`: `passed-by-owner-confirmation`

## 完成后应具备的能力

- 解释 Batch 为什么是 Agent 动作的确定性业务边界。
- 沿真实 HOLD 链路定位原因规范化、证据验证、事务、行锁与条件 SQL。
- 区分外键能保证的存在性与 Java 必须保证的关系/异常语义。
- 解释为何 HOLD 条件更新足够，而 Inspection 创建需要锁定父 Batch。
- 根据 SQL 影响行数、响应和数据库首次证据调试并发覆盖。

## 编码前讲解清单

- [x] 业务问题与工程问题
- [x] 组件边界与所有权
- [x] 数据流和状态迁移
- [x] 事务、并发和关键不变量
- [x] 失败、重试、幂等和恢复路径
- [x] 测试与可观测性策略
- [x] 替代方案与取舍

## 真实 Code Walkthrough 路线

实现后填写 Batch 创建、HOLD、Inspection 创建与内部 RELEASE 的真实 Controller、Application、Domain、Repository、Flyway 和测试符号。

## 项目所有者亲自修改任务

- 任务：为 Batch 查询响应增加 `inspection_count`，在只读事务中组合 Batch 与 Inspection 数量并覆盖 0、1、2。
- 为什么需要理解：必须判断聚合查询属于 Inspection Repository，并理解只读查询模型的组合边界。
- 验收方法：真实 MySQL HTTP 测试和全套回归通过。
- 安全边界：不得修改状态迁移、写事务、行锁、条件更新、唯一键或外键。

## Failure/Debug Exercise

- 注入故障：从 HOLD 更新 SQL 删除 `AND status='OPEN'`。
- 操作步骤：并发提交两个不同原因/证据的 HOLD。
- 预期行为：测试捕获两个调用误判成功或首次 `held_at`、原因、证据被后到事务覆盖。
- 观察证据：SQL 影响行数、两个 disposition、数据库最终首次字段和失败断言。
- 常见错误行为：Java 先判断状态后执行无条件更新，误以为读取结果不会过期。
- 清理/复位：恢复条件并运行并发及完整测试。
- 完成后应能回答：条件 SQL 保护了什么；为何父行锁和条件更新不是同一种用途。

## Learning Gate

- [x] 能解释真实设计和关键取舍。
- [x] 能沿成功调用链定位核心代码。
- [x] 能定位并解释至少一条失败路径。
- [x] 已亲自完成约定的小修改：Batch 查询增加 `inspection_count`。
- [x] 已完成故障实验并根据证据判断结果。
- [x] 能指出事务、幂等、权限和恢复逻辑的实际执行位置。
- [x] 已 review 最终 diff 并明确接受。

项目所有者于 2026-08-13 明确确认本 Change 的 Learning Gate 已完成。

## 会话边界

实现会话连续实现到 handoff；独立 Review/Learning 会话完成 Walkthrough、owner 修改、故障实验和最终验收。两个会话不得同时修改本 Change/worktree。
