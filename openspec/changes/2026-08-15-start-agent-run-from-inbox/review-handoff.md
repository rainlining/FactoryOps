# Review Handoff：2026-08-15-start-agent-run-from-inbox

## 元数据

- `change_id`: `2026-08-15-start-agent-run-from-inbox`
- `learning_level`: `deep`
- `status`: `draft-not-executable`
- `feature_branch`: `codex/start-agent-run-from-inbox`
- `worktree`: `C:\Users\小霖\Desktop\work\project2\FactoryOps\.worktrees\start-agent-run-from-inbox`
- `base_commit`: `db7ab6e`
- `head_commit`: 全量验证与最终审查后填写

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

## 尚未满足的 Handoff 条件

- Docker 当前未运行，真实 MySQL/Kafka 与完整回归尚未执行。
- 尚未进行最终独立只读代码审查。
- 最终 head commit 与完整验证数量尚未填写。

在这些条件满足前，本文件不得作为 Review/Learning 会话的执行依据，也禁止另一会话并发修改当前 worktree。
