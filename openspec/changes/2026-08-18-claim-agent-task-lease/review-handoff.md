# Review Handoff

- Change：`2026-08-18-claim-agent-task-lease`
- 学习等级：`deep`
- 状态：`review-handoff-ready`
- 分支：`codex/claim-agent-task-lease`
- worktree：`C:\\Users\\小霖\\Desktop\\work\\project2\\FactoryOps\\.worktrees\\claim-agent-task-lease`
- base：`3df4c3dff05042e48f9892c1749a505fc48891c9`

## 范围与路线

新增 migration 006 `agent_task_leases` 和 `task_lease.py::AgentTaskLeaseService`。阅读顺序：proposal/design → migration → `claim` → `renew` → `release` → `test_task_lease_claim_renew_release`。

成功链：锁 PENDING Task → 锁/读取 lease → 无有效 lease 时生成随机 token并写 owner/expiry → renew 条件匹配 task/owner/token/未过期 → release 条件匹配后删除。

失败链：非 PENDING、未过期竞争、TTL/owner 非法、过期或陈旧 token 均拒绝；旧 owner 无法删除新 owner 接管后的 lease。

## 验证与 Review

- Agent 全量 116 passed；真实 lease/dispatch 5 passed；Ruff 通过。
- Important 时区问题已修复，复审无 Critical/Important。
- 非目标：Task RUNNING、Execution、Worker runtime、Redis、retry、LLM/Tool、Checkpoint/Resume、`dataset/`。

Owner 修改：调整 TTL 上限边界并运行局部测试。Failure exercise：让 lease 过期后由 worker-2 接管，再用 worker-1 的旧 token release，必须被拒绝且 worker-2 lease 保持。完成 Walkthrough、Owner 修改、故障实验和最终 diff 接受前，不得归档或合并 main。
