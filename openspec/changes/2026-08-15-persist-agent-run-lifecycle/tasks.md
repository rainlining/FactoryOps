# Change 任务：2026-08-15-persist-agent-run-lifecycle

## 设计

- [x] 完成 Schema、事务、状态图、幂等、并发、时间和所有权设计。
- [x] 项目所有者批准完整设计。
- [x] 编写 OpenSpec 与实施计划。

## 实现

- [x] Task 1：修正 CANCELLED Contract 时间语义并以 Contract 测试保护。
- [x] Task 2：实现领域命令、结果类型与确定性迁移规则。
- [x] Task 3：升级 migration runner 并创建 Run/Transition Schema。
- [x] Task 4：实现 original/replay 创建事务与读取重建。
- [x] Task 5：实现状态迁移、乐观锁和 request 幂等分类。
- [x] Task 6：完成 MySQL 并发、故障回滚、回归和 handoff。

## Handoff

- [ ] 推送 feature branch；本地 handoff 已准备，GitHub 网络阻断记录在 `verification.md`。
- [ ] 独立 Review/Learning 会话完成 Deep Learning Gate。
