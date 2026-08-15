# Review Handoff：2026-08-15-start-agent-run-from-inbox

## 元数据

- `change_id`: `2026-08-15-start-agent-run-from-inbox`
- `learning_level`: `deep`
- `status`: `review-handoff-ready`
- `feature_branch`: `codex/start-agent-run-from-inbox`
- `worktree`: `C:\Users\小霖\Desktop\work\project2\FactoryOps\.worktrees\start-agent-run-from-inbox`
- `base_commit`: `db7ab6e`
- `reviewed_implementation_head`: `f217b7e`
- `handoff_metadata_commit`: 本文件的最终文档提交；用 `git log -1 --oneline` 取得

## 已实现范围

- 启动时冻结七个 Agent 版本字段，并生成 original Run Provenance。
- 将解码后的 Incident 显式传给 `IncidentRunStarter`。
- 对 `accepted` 和 `duplicate-identical` Inbox outcome 创建或确认唯一 Run。
- Run 完成后才提交 Kafka offset；retryable 失败 seek/retry，完整性失败退出。
- 记录 `run_id` 与 `run_start_outcome`。

非目标：Coordinator、Run `RUNNING`、LLM、Tool、Inbox 状态/Lease、Redis、数据库 migration。

## 真实调用链

1. 入口：`event_ingress.main.main` 校验配置并组装 Consumer、Processor、Starter。
2. Kafka ownership：`KafkaIngressWorker.run_once` poll record。
3. Contract：`KafkaRecordDecoder.decode` 校验事件并生成 `DecodedEvent.incident_id`。
4. Inbox 事务：`EventIngressProcessor.process` 调用 `MySqlInboxRepository.accept/reject`。
5. Run 事务：可信 outcome 调用 `IncidentRunStarter.ensure_original_run`，再进入 `AgentRunLifecycleService.create_original_run`。
6. 持久化：Lifecycle 在一个事务中写 `agent_runs` snapshot 与 initial `agent_run_transitions`。
7. offset：Processor 成功返回后，Worker 才执行 synchronous commit。

失败链：Inbox commit 后 Run 失败时 Worker seek 并抛出；main 对 adapter 故障 sleep/retry。重投被 Inbox 分类为 `duplicate-identical` 后仍调用 Starter。Incident/Contract 完整性错误转换为 `RunStartIntegrityError`，main 不重试并退出。

## 建议 Review 顺序

1. OpenSpec `spec.md`、`design.md`。
2. `runtime_config.py`、`model.py`、`decoder.py`。
3. `run_starter.py`、`processor.py`。
4. `worker.py`、`main.py`。
5. `test_inbox_mysql.py`、`test_kafka_mysql_e2e.py`。

## Learning Gate 任务

- Owner 修改：在 Review 会话确定一个需要理解 offset 完成不变量的小型可观察字段或失败分类修改。
- Failure/Debug Exercise：注入 Inbox commit 后、Run 创建前一次失败；观察 Inbox=1、Run=0、offset 未提交，复位后重投得到 Inbox=1、Run=1、initial history=1、offset 已提交。

## 验证与审查

- Agent Service：75 passed；Ruff check/format 通过。
- Contract：57 passed。
- Java `mvn verify`：65 passed，0 failures/errors/skipped。
- `git diff --check`：通过。
- 独立复审：READY，0 Critical、0 Important、0 Minor。
- 完整命令、耗时和首次审查修复记录见 `verification.md`。

## Review 会话恢复

```powershell
cd C:\Users\小霖\Desktop\work\project2\FactoryOps\.worktrees\start-agent-run-from-inbox
git status --short --branch
git log --oneline db7ab6e..HEAD
git diff --stat db7ab6e..HEAD
```

Review/Learning 会话只读恢复后，先完成 Walkthrough，再由项目所有者执行 Owner 修改和 Failure/Debug Exercise。不得与实现会话并发修改该 worktree。

## 剩余风险

- 固定 1 秒 retry delay 没有指数退避；当前只用于已有同步 Worker 的 adapter 重试。
- 本 Change 不领取或执行 `PENDING` Run；后续 Coordinator Change 必须定义 ownership 与恢复。
- Learning Gate 尚未完成，Change 不得标记 `completed`、归档或合并 `main`。
