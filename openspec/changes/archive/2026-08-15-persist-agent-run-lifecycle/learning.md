# Learning Plan：2026-08-15-persist-agent-run-lifecycle

## 元数据

- `learning_level`: `deep`
- `status`: `passed`

## 学习目标

1. 沿 original 创建与状态迁移两条真实事务调用链定位代码。
2. 解释唯一键、外键、CHECK、领域规则和 Application Service 各自保护什么。
3. 解释乐观锁为什么同时检查 status/revision，以及冲突为什么不自动重试。
4. 解释 history INSERT 失败为什么必须回滚 snapshot UPDATE。
5. 区分 duplicate-identical、duplicate-conflicting 和 concurrency-conflict。

## Owner 修改任务

在 Review 会话中增加一个合法或非法迁移边，并同步修改领域规则与精确测试；任务必须要求解释该边的业务含义和终态影响，不得只是改名。

## Failure/Debug Exercise A：并发冲突

- 注入：两个命令基于同一 revision 并发迁移到不同状态。
- 预期：最多一个 applied，另一个 concurrency-conflict。
- 观察：最终 snapshot revision、transition 数量和失败结果。
- 复位：测试容器结束后自动销毁数据库。
- 回答：为什么不应自动重放失败命令。

## Failure/Debug Exercise B：历史写入失败

- 注入：让 transition INSERT 违反约束或由测试故障点抛错。
- 预期：snapshot UPDATE 与 transition INSERT 整体回滚。
- 观察：状态、revision 和 history count 均保持原值。
- 复位：撤销故障注入并重跑测试。
- 回答：为什么不能在捕获 INSERT 异常后提交原事务。

## Learning Gate

- [x] 解释真实设计与关键取舍。
- [x] 完成两条真实调用链 Walkthrough。
- [x] 定位并解释创建和迁移失败路径。
- [x] 完成 Owner 修改任务。
- [x] 完成两项 Failure/Debug Exercise。
- [x] 指出事务、幂等、乐观锁和不可变字段实际执行位置。
- [x] Review 最终 diff 并明确接受。

## 完成记录

2026-08-15，项目所有者确认两条真实事务链 Walkthrough 与故障实验证据已经完成，并要求在修复最终 Diff Review 阻塞项、确认无问题后归档。最终实现经过多轮独立只读审查；Head `a415350` 的结论为 0 Critical、0 Important，Learning Gate 通过。
