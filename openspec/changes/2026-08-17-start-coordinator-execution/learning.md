# Change 学习计划

- `learning_level`: `deep`
- `gate_status`: `not-started`

Review 应能解释为什么启动必须跨两个聚合单事务、receipt 与两类 history 的职责差异、Run 行锁和 request key 各自解决什么问题，以及提交结果不确定时如何恢复。

## Owner 亲自修改

在 Review 会话中为启动命令的 evidence refs 增加一个非空合法边界测试，解释其是否应影响幂等 payload 摘要，并运行局部测试。Codex 不预先代做。

## Failure/Debug Exercise

- 注入：让 Run history INSERT 抛错。
- 预期：Execution snapshot/history、Run 更新和 receipt 全部不可见。
- 证据：四张领域表和 receipt 的行数/状态查询。
- 常见错误：Execution 已提交但 Run 仍 PENDING，或 Run RUNNING 但 receipt 缺失。
- 清理：测试事务/独立测试 Run 自动隔离，无生产数据清理。
- 应能回答：为什么两个现有 Service 顺序调用无法提供同等保证。

Learning Gate 在真实 Walkthrough、Owner 修改、故障实验和最终 diff 接受前保持未通过。
