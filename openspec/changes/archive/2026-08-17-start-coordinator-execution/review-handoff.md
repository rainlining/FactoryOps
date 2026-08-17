# Review Handoff

## 恢复信息

- Change：`2026-08-17-start-coordinator-execution`
- 学习等级：`deep`
- 状态：`completed`
- 分支：`codex/start-coordinator-execution`
- worktree：`C:\\Users\\小霖\\Desktop\\work\\project2\\FactoryOps\\.worktrees\\start-coordinator-execution`
- original base commit：`8e73eb57a269dc453c78152f84d6a547fd02f633`
- reviewed upstream tree：`49561e83739bc17a45c297043a11fae4bfc96305`
- reviewed implementation head：`3a0a9b9486ff0513ce38cd7c58726f302cedcb55`
- final handoff commit：以该分支远端 HEAD 为准

该分支堆叠在 `codex/persist-agent-execution-lifecycle` 上。Review 期间禁止其他会话并发修改此 Change/worktree；上游 Deep Change 仍受各自 Learning Gate 约束。

## 已实现与非目标

已实现 version 1.0.0 启动命令、migration 005 receipt、request payload SHA-256、Run 行锁、Coordinator Execution 创建、Run PENDING→RUNNING、两类 history 与 receipt 的单事务提交、相同/冲突重放、同 Run 并发单赢家和提交结果恢复。

非目标：Redis lease/owner、心跳与接管、Task dispatch、专业 Agent、LLM/Tool、Context 内容、Checkpoint/Resume、Java API、Evaluation、`dataset/`。

## Walkthrough 路线

1. `proposal.md`、`design.md`：跨聚合事务不变量与非目标。
2. `coordinator_start/model.py::StartCoordinatorCommand`：版本化请求和四类结果。
3. `coordinator_start/service.py::CoordinatorStartService.start`：request 查重、Execution/Run candidate Contract 校验、事实构造、竞态分类和 reload。
4. `coordinator_start/repository.py::MySqlCoordinatorStartRepository.start`：Run `FOR UPDATE`、Execution snapshot/history、Run 条件更新/history、receipt 的同事务顺序。
5. `005_create_coordinator_start_requests.sql`：request/Run/Execution 唯一约束和 RESTRICT FK。
6. `test_coordinator_start_mysql.py`：成功、幂等、并发、非法输入、失败回滚与预存 Execution key 冲突。

成功链：`start` → request digest/receipt lookup → Run/Execution Contract candidate → Repository Run lock → Execution snapshot/history → Run RUNNING update/history → receipt → commit → Contract reload。

失败链：非法输入在写前拒绝；Run 不可启动返回 concurrency conflict；相同 request 由 receipt 分类；Execution key 竞争重读赢家；任一事务写失败整体回滚。

## 验证与风险

- Contract 99 passed；Agent 116 passed；Java 65 passed；Ruff 通过。
- 独立审查 1 Important 已修，复审无 Critical/Important。
- 真实命令、RED 过程和数据库证据见 `verification.md`。
- 剩余风险：只有瞬时数据库互斥，没有长期 Worker ownership；Context Snapshot 的存在性尚无本地 FK；当前 use case 通过既有 Service 的 Contract 重建方法校验数据库对象，后续可抽取公开 serializer，但本 Change 不做无关重构。

## Deep Learning Gate

Owner 修改已由 Codex 按项目所有者授权代做：单 evidence ref 会持久化，改变 evidence 会得到 `duplicate-conflicting`，证明 evidence 参与 payload digest。局部测试 `7 passed`。按现行 `AGENTS.md`，这不能记作项目所有者亲自完成。

Failure/debug 已实际完成：注入 Run history INSERT 失败；Run 仍 PENDING，Run history 仅 1 条初始记录，Execution snapshot/history 与 receipt 均不可见。两个现有 Service 若顺序调用会各自提交事务，第二步失败无法回滚第一步；当前 Repository 用一个事务覆盖全部写入。

最终 diff review 已完成：相对更新后的上游树仅包含本 Change 工件、005 migration、Coordinator Start 实现和测试；`dataset/` 未修改，`git diff --check` 通过，无新增 Critical/Important。

真实 Walkthrough、Owner 修改、故障实验与最终 diff review 已完成；后续 Review/Learning 会话已记录项目所有者最终接受，归档状态为 `completed`。
