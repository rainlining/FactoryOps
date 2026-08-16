# Review Handoff：2026-08-16-define-agent-execution-contract

## 元数据

- `change_id`: `2026-08-16-define-agent-execution-contract`
- `learning_level`: `deep`
- `status`: `review-handoff-ready`
- `feature_branch`: `codex/define-agent-execution-contract`
- `worktree`: `C:\Users\小霖\Desktop\work\project2\FactoryOps\.worktrees\define-agent-execution-contract`
- `base_commit`: `f2fc6b7b16fadb0f208fcdfabae72bb99f7730f6`
- `reviewed_implementation_head`: `aed474706f795e1702ae2505d88a579a507117dd`
- `handoff_metadata_commit`: 本文件所在最终文档 commit；恢复后用 `git log -1 --oneline` 获取

## 已实现范围

- Agent Execution Contract v1.0.0 严格 JSON Schema。
- 五种正式角色、Specialist Task 要求、包含 Task 的确定性 key 和 attempt 语义。
- 冻结 Provenance、PENDING/RUNNING/终态 shape、result/failure 互斥和时间不变量。
- canonical form 与 identical、next revision、conflicting、distinct 分类。
- 合法/非法 fixtures、18 项测试、README 和中文 OpenSpec/技术选型。

非目标：数据库、migration、Run claim/lease、Coordinator/Task runtime、LLM、Tool、Checkpoint/Resume/Replay 执行、Java API、Evaluation 和 `dataset/`。

## 关键决定

- Run 拥有整体工作流；Execution 只拥有一个角色的一个 Task attempt。
- retry 创建新 Execution/attempt，不覆盖历史失败。
- key 摘要包含 version、Run、role、Task-or-dash、attempt，允许同角色处理多个 Task。
- Provenance 记录实际执行版本，不从父 Run 静默推断。
- 大型内容和完整 Task/Context/Artifact 只以引用表达。
- relation classifier 不替代数据库事务和乐观锁。

## 真实调用路线

1. Fixture 入口：`contracts/agent_execution/fixtures/valid/*.json`。
2. 结构边界：`contracts/agent_execution/v1.0.0/schema.json`。
3. 校验入口：`validator.validate_execution`，依次处理版本、Schema、key/Task/ref/time。
4. 幂等：`compute_execution_key` 生成规范摘要。
5. 比较：`canonicalize_execution` 与 `classify_execution_relation`。
6. revision：`_is_next_revision` 检查 immutable 区域、+1、合法状态边、时间与 `started_at`。
7. 错误：`AgentExecutionValidationError.issues` 提供稳定 code/path/message。
8. 测试：`test_schema.py`、`test_validator.py`。

成功链：payload → supported version → strict Schema → semantic validation → canonical bytes/relation。

失败链：unsupported version 提前拒绝；未知/ground truth 被 Schema 拒绝；key、Task、重复引用和时间错误由 Validator 拒绝；immutable 变化、revision 跳跃、非法状态边或 `started_at` 改写分类为 conflicting。

## 验证与审查

- 新 Contract：18 passed；Ruff 通过。
- 全部 Contract：75 passed。
- Agent Service：75 passed，真实 MySQL/Kafka；Ruff 通过。
- Java：65 passed，0 failures/errors/skipped。
- 独立审查：2 Important 已在 `aed4747` 修复；当前 0 Critical、0 Important、0 Minor。
- 完整命令和环境事件见 `verification.md`。

## Review/Learning 任务

Owner 修改：按 `learning.md` 调整 failure message 最大长度，同步 Schema、边界测试和 README；不得改变 recoverability、生命周期或 key。

Failure/debug exercise：修改 Specialist fixture 的 attempt 或 task_id 但保留旧 key，观察 `execution_key_mismatch` 与 `$.identity.execution_key`；用 helper 重算后通过。

建议阅读顺序：proposal/规格/技术选型 → Schema/fixtures → Validator → tests → verification/final diff。

## 恢复命令

```powershell
cd C:\Users\小霖\Desktop\work\project2\FactoryOps\.worktrees\define-agent-execution-contract
git status --short --branch
git log --oneline f2fc6b7..HEAD
git diff --stat f2fc6b7..HEAD
python -m pytest contracts/agent_execution/tests -q
```

该 worktree 现在只供 Review/Learning 会话使用。不得并发修改。Deep Learning Gate 通过前不得归档、合并 `main` 或删除分支/worktree。

## 剩余风险

- 数据库唯一约束、引用存在性、状态事务、claim/lease 和 retry policy 尚未实现。
- Contract 不证明 Agent 输出业务正确，只证明结构、身份和生命周期一致。
- Learning Gate、Owner 修改和 failure/debug exercise 均待独立会话完成。
