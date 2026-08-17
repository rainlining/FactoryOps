# Review Handoff

- Change：`2026-08-17-claim-agent-task-lease`
- 学习等级：`deep`
- 状态：`review-handoff-ready`
- 分支：`codex/claim-agent-task-lease`
- worktree：`C:\\Users\\小霖\\Desktop\\work\\project2\\FactoryOps\\.worktrees\\claim-agent-task-lease`
- base / Dispatch upstream：`af23d07fa94355508378f3561fc505f08f18285c`
- upstream integration merge：`e8f47ebef8e25ea46e5f090ae165d4fc4bca2252`
- original claim head：`9a1ded41e3d3cb91233fc433a4203492fe68f79f`
- final handoff head：以该分支最新远端 HEAD 为准

该分支已吸收最新 Dispatch，以及其包含的 Coordinator Start 和 Execution integrity Review 修复；没有修改任何上游 worktree。migration 版本为 001→006，lease migration 与上游 preflight/约束兼容。

## 范围与路线

新增 migration 006 `agent_task_leases` 和 `task_lease.py::AgentTaskLeaseService`。阅读顺序：proposal/design → migration → `claim` → `renew` → `release` → `test_task_lease_claim_renew_release`。

成功链：锁 PENDING Task → 锁/读取 lease → 无有效 lease 时生成随机 token并写 owner/expiry → renew 条件匹配 task/owner/token/未过期 → release 条件匹配后删除。

失败链：非 PENDING、未过期竞争、TTL/owner 非法、过期或陈旧 token 均拒绝；旧 owner 无法删除新 owner 接管后的 lease。

## 验证与 Review

- Agent 全量 122 passed；真实 lease/dispatch 6 passed；Contract 99；Java 65；Ruff 通过。
- 时区、renew TTL 和陈旧 token fencing 问题已修复，复审无 Critical/Important。
- 非目标：Task RUNNING、Execution、Worker runtime、Redis、retry、LLM/Tool、Checkpoint/Resume、`dataset/`。

Owner 修改：调整 TTL 上限边界并运行局部测试。Failure exercise：让 lease 过期后由 worker-2 接管，再用 worker-1 的旧 token release，必须被拒绝且 worker-2 lease 保持。完成 Walkthrough、Owner 修改、故障实验和最终 diff 接受前，不得归档或合并 main。
