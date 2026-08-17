# Change 学习计划

- `learning_level`: `deep`
- `gate_status`: `completed-externally`

Review 应能解释为什么启动必须跨两个聚合单事务、receipt 与两类 history 的职责差异、Run 行锁和 request key 各自解决什么问题，以及提交结果不确定时如何恢复。

## Owner 亲自修改

已由 Codex 代做：增加仅含一个合法 evidence ref 的边界测试，证明该引用会持久化到 Execution input，并证明同一 `start_request_id` 只要 evidence 改变就返回 `duplicate-conflicting`。evidence 是确定性启动输入，因此必须参与 payload digest。局部测试 `7 passed`。

根据项目所有者最新授权，今后的 Owner 修改可由 Codex 执行；但当前 `AGENTS.md` 仍要求 Deep Change 由项目所有者亲自修改。本次任务只能记为“Codex 代做并验证”，不能记作项目所有者亲自完成，除非后续通过独立治理 Change 修改该规则。

## Failure/Debug Exercise

- 注入：让 Run history INSERT 抛错。
- 预期：Execution snapshot/history、Run 更新和 receipt 全部不可见。
- 证据：四张领域表和 receipt 的行数/状态查询。
- 常见错误：Execution 已提交但 Run 仍 PENDING，或 Run RUNNING 但 receipt 缺失。
- 清理：测试事务/独立测试 Run 自动隔离，无生产数据清理。
- 应能回答：为什么两个现有 Service 顺序调用无法提供同等保证。

Learning Gate 当前仍未通过；已完成项和剩余治理条件见下方记录。

本次故障实验已实际完成：固定待创建 Execution ID，并注入 Run history INSERT 异常。数据库证据为 Run `PENDING/revision 0/coordinator_execution_id NULL`、Run history 仍为初始 1 条、Execution snapshot/history 均为 0、receipt 为 0。测试 `test_run_history_failure_rolls_back_everything` 通过，无需清理生产数据。

Codex 已完成最终 diff review，未发现新的 Critical/Important；项目所有者最终明确接受与现行 Owner 亲自修改治理条件仍未完成。
