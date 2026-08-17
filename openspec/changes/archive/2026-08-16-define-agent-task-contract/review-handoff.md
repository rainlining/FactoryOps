# Review Handoff：2026-08-16-define-agent-task-contract

## 元数据

- `change_id`: `2026-08-16-define-agent-task-contract`
- `learning_level`: `deep`
- `status`: `completed`
- `feature_branch`: `codex/define-agent-task-contract`
- `worktree`: `C:\Users\小霖\Desktop\work\project2\FactoryOps\.worktrees\define-agent-task-contract`
- `stacked_on_branch`: `codex/define-agent-execution-contract`
- `stacked_base_commit`: `d6b4ca8338c97f05e2413982e40f26aa66864f71`
- `reviewed_implementation_head`: `4d9500189c073a0cfbc4ad3d475cfb072ebee5bc`
- `handoff_metadata_commit`: 本文件所在最终文档 commit

## 实现与非目标

已实现 Agent Task v1.0.0：四类专业 Task/type-role 映射、Run 内 dispatch request/key 幂等、输入/依赖引用、六状态生命周期、Execution 摘要、终态 completion/failure、时间/revision 关系、strict Schema、fixtures、Validator 和 22 项测试。

非目标：数据库、migration、依赖图持久化、Coordinator/parallel Worker、Execution 创建、retry policy、LLM/Tool、Run lease、Java API、Evaluation、`dataset/`。

## 关键决定与调用路线

- Run 拥有 Workflow；Coordinator Execution 创建 Task；Task 拥有工作要求；Execution 拥有 attempt。
- request ID/key 防止 dispatch 重投；相同 key 不同 Task ID 是冲突。
- retry 保持 Task RUNNING 并新增 Execution；Task FAILED 只表示已无合法 retry。
- type/role 固定，input 和依赖在 revision 间不可变。

真实路线：valid fixture → `v1.0.0/schema.json` → `validate_task` 的版本/Schema/key/type-role/dependency/terminal/time 校验 → `canonicalize_task` → `classify_task_relation` → `_is_next` 的 revision/状态/attempt 检查。错误通过 `AgentTaskValidationError.issues` 返回 code/path/message；测试入口为 `test_schema.py` 与 `test_validator.py`。

## 验证与审查

- Task 22 passed；全部 Contract 97 passed。
- Agent Service 75 passed，真实 MySQL/Kafka；Ruff 通过。
- Java 65 passed。
- 独立审查 1 Important 已在 `4d95001` 修复；当前 0 Critical/Important/Minor。
- 完整命令见 `verification.md`。

## 两个 Change 的 Review 顺序

1. 先在 Execution worktree review `2026-08-16-define-agent-execution-contract`，完成其 Walkthrough、Owner 修改、故障实验和 Learning Gate。
2. Execution Change 合并或其最终 review commit 进入本 stacked branch 后，再 review本 Task Change。
3. 若 Execution Review 产生代码 commit，本 Task 分支须 rebase/merge 该最终 commit 并重跑验证；不得直接忽略 stacked base 差异。
4. 两个 worktree 不得由多个会话并发修改。

## 本 Change Learning 任务

Owner 修改：调整 Task failure message 长度边界，同步 Schema、测试和 README，不改变 key/状态/role/retry。

Failure/debug：修改合法 Task 的 `task_request_id` 但保留 key，观察 `task_key_mismatch` 与 `$.identity.task_key`；调用 helper 重算后通过。

## 恢复命令

```powershell
cd C:\Users\小霖\Desktop\work\project2\FactoryOps\.worktrees\define-agent-task-contract
git status --short --branch
git log --oneline d6b4ca8..HEAD
git diff --stat d6b4ca8..HEAD
python -m pytest contracts/agent_task/tests -q
```

本 worktree 现在只供 Review/Learning 使用。Learning Gate 前不得归档、合并 `main` 或删除分支/worktree。

## 剩余风险

- 跨对象 role/status/引用存在性和依赖 DAG 尚无数据库证明。
- 并发 dispatch、状态事务、attempt 创建和恢复尚未实现。
- 两个 stacked Change 均需各自通过 Learning Gate，不能因联合 review 跳过任一 Gate。

## Review/Learning 会话增量（2026-08-17）

- 已完成真实调用链 Walkthrough 和 failure/debug exercise。
- 已吸收 Execution Review commit。
- 项目所有者要求 Codex 代做 Owner 修改；Task `failure.message` 上限已改为 600，并补 600/601 边界测试和 README。
- 本次代做不算项目所有者亲自完成，因此 Deep Learning Gate 仍未通过。
- 增量验证：Task tests 23 passed；全部 Contract 99 passed；Ruff check/format 通过。
- Persistence stacked branch 必须吸收本分支并把数据库 `failure_message` 容量同步到 600 后重新验证。
