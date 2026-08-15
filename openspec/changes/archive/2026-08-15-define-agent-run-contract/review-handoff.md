# Review Handoff：2026-08-15-define-agent-run-contract

## 1. Handoff 身份

- `change_id`: `2026-08-15-define-agent-run-contract`
- `learning_level`: `deep`
- `status`: `archived`
- `feature_branch`: `codex/define-agent-run-contract`
- `worktree`: `C:\Users\小霖\Desktop\work\project2\FactoryOps\.worktrees\define-agent-run-contract`
- `base_commit`: `651228b9d71ee81e80e6a5030e4c49a50ec60f88`
- `owner_change_commit`: `0dfe007c48710810c2ed94ecd09a0c6d93d89b20`
- `review_fix_commit`: `662f20983e00a6aa4d6faea2eaf8b21a160d2a37`
- `review_scope`: 上述 review fix commit 包含全部 Contract 行为、测试和 Owner 修改；其后提交只同步完成与归档文档。

Review/Learning 会话接手期间，不得由其他会话修改本分支或 worktree。

Feature branch 已推送到 `origin/codex/define-agent-run-contract`，可以由独立 Review/Learning 会话接手。

## 2. 已实现范围

- Workflow Run v1.0.0 严格 JSON Schema。
- original/replay 有效 fixtures 与关键非法 fixtures。
- 结构化 Validator：版本前置、Schema path、身份、replay 自引用、时间顺序和进度校验。
- canonical JSON 与 `duplicate-identical`、`duplicate-conflicting`、`distinct` 关系分类。
- 中文 Contract README、OpenSpec、实施计划与验证证据。

## 3. 明确非目标

- 未创建 MySQL 表、Repository、状态迁移或乐观锁实现。
- 未修改 Kafka Consumer，也未从 Inbox 创建 Run。
- 未实现 Coordinator、Agent Runtime、Agent Execution、Task、Checkpoint、Resume 或 Replay 执行。
- 未实现 Prompt、Model、Tool、Context 或 Evaluation 能力。
- 未修改 `dataset/`。

## 4. 关键设计决定

- `Workflow Run` 表示完整 Incident 工作流；单 Agent 调用保留为 `Agent Execution`。
- original 以 `trigger_event_id` 幂等，replay 以 `replay_request_id` 幂等，`run_id` 只负责引用。
- replay 同时记录根 `original_run_id` 和直接 `replayed_from_run_id`。
- `identity`、`provenance` 不可变，`lifecycle` 使用 revision 演进。
- 审批等待与可恢复技术暂停分别为 `WAITING_FOR_APPROVAL`、`SUSPENDED`。
- 所有对象拒绝未知字段，不提供自由 metadata；ground truth 被隔离。
- 单条 Contract 不伪装验证数据库唯一性、引用存在性或跨记录循环。

## 5. 建议阅读顺序

1. `openspec/changes/2026-08-15-define-agent-run-contract/design.md`
2. `contracts/agent_run/README.md`
3. `contracts/agent_run/fixtures/valid/original-run.json`
4. `contracts/agent_run/fixtures/valid/replay-run.json`
5. `contracts/agent_run/v1.0.0/schema.json`
6. `contracts/agent_run/validator.py`
7. `contracts/agent_run/tests/test_schema.py`
8. `contracts/agent_run/tests/test_validator.py`
9. `openspec/changes/2026-08-15-define-agent-run-contract/learning.md`

## 6. 真实成功调用链

```text
调用方提供 Mapping
→ validate_run(run)
→ 读取并检查 contract_version
→ _schema_for(version) 加载 v1.0.0/schema.json
→ Draft202012Validator 校验严格结构和条件字段
→ 校验 original/replay 身份不变量
→ 校验 lifecycle 时间顺序
→ 校验 progress 完成数
→ 合法返回 None
```

关系分类链：

```text
classify_run_relation(first, second)
→ canonicalize_run(first) → validate_run(first)
→ canonicalize_run(second) → validate_run(second)
→ 比较 identity.run_id
→ 比较 canonical UTF-8 bytes
→ 返回 distinct / duplicate-identical / duplicate-conflicting
```

核心符号：

- `contracts.agent_run.validator.validate_run`
- `contracts.agent_run.validator._schema_error_path`
- `contracts.agent_run.validator.canonicalize_run`
- `contracts.agent_run.validator.classify_run_relation`
- `contracts.agent_run.validator.AgentRunValidationError`

## 7. 失败调用链

以 replay 自引用为例：

```text
replay-self-reference.json
→ 版本与 Schema 结构合法
→ validate_run 进入 replay 语义分支
→ replayed_from_run_id == run_id
→ 抛出 AgentRunValidationError
→ issue.code = replay_self_reference
→ issue.path = $.identity.replayed_from_run_id
```

非法输入进入 relation classifier 时，会先经过 `canonicalize_run` 调用的 `validate_run`，因此不会得到任何关系分类。

## 8. 实际验证

```powershell
python -m ruff check contracts/agent_run
python -m ruff format --check contracts/agent_run
python -m unittest discover -s contracts -p "test_*.py" -v
git diff --check
```

结果：

- Ruff check：通过。
- Ruff format：6 个 Python 文件均已格式化。
- Contract tests：55/55 通过，其中 Agent Run 20 个。
- `git diff --check`：通过。

## 9. 已知限制与剩余风险

- 幂等键唯一性、引用存在性、跨记录 replay 环必须由后续 MySQL Change 验证。
- 当前只冻结状态含义和快照组合，没有冻结状态迁移图。
- `revision` 尚未连接 Repository 的 compare-and-set 更新。
- relation classifier 将同 `run_id` 的不同合法内容判为冲突；正常 Lifecycle 演进必须由后续 Repository 依据 revision 处理，不能误用该传输重复分类器。

## 10. Owner 修改任务（已完成）

项目所有者已在 `0dfe007` 中把 `status_reason.code` 最小长度收紧为 3，并增加 `short-status-reason-code.json` 失败 fixture。

完成结论：

- 修改拒绝无法表达稳定含义的单字符原因码。
- fixture relation test 会在约束被撤销时失败。
- v1.0.0 尚未发布，本次为首版冻结前收紧，不触发 major 升级。

## 11. Failure/Debug Exercise

- 注入：把合法 replay 的 `replayed_from_run_id` 改成自身 `run_id`。
- 预期：`replay_self_reference`，路径 `$.identity.replayed_from_run_id`。
- 观察：Validator 错误和 relation classifier 的前置拒绝。
- 常见错误：只校验字段存在；或把非法输入分类为 `distinct`。
- 复位：恢复 `RUN-22222222222222222222222222222222` 并重新运行测试。
- 完成后回答：为什么单条 Validator 能发现自引用，却不能发现 A→B→C→A 的跨记录循环。

## 12. Review 会话恢复命令

```powershell
Set-Location 'C:\Users\小霖\Desktop\work\project2\FactoryOps\.worktrees\define-agent-run-contract'
git status --short
git log --oneline 651228b9d71ee81e80e6a5030e4c49a50ec60f88..HEAD
git diff --stat 651228b9d71ee81e80e6a5030e4c49a50ec60f88..HEAD
python -m unittest discover -s contracts -p "test_*.py" -v
```

完成 Deep Learning Gate、Owner 修改、Failure/Debug Exercise 和最终 diff 接受前，不得将 Change 标记 `completed`，不得归档或合并 `main`。
