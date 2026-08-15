# FactoryOps Agent Service

当前实现可靠的 Kafka Event Ingress，并在可信质量事件提交 offset 前确保其拥有唯一 `PENDING` original Agent Run。不包含 Coordinator、Agent 执行、LLM、Tool 或 HTTP API。

## 安装与测试

```powershell
cd services/agent-service
python -m pip install -e ".[test]"
python -m ruff check .
python -m ruff format --check .
python -m pytest -q
```

完整测试会通过 Docker 启动 MySQL 8.4 和 Apache Kafka 4.1.0。

## 运行

先准备专用于 Agent Service 的 MySQL database，并启动仓库中的 Kafka 环境：

```powershell
$env:FACTORYOPS_AGENT_DATABASE_URL = "mysql+pymysql://user:password@localhost:3306/factoryops_agent"
$env:FACTORYOPS_KAFKA_BOOTSTRAP_SERVERS = "localhost:19092"
$env:FACTORYOPS_AGENT_RUNTIME_VERSION = "agent-runtime:0.1.0"
$env:FACTORYOPS_AGENT_WORKFLOW_VERSION = "incident-workflow:0.1.0"
$env:FACTORYOPS_AGENT_PROMPT_SET_VERSION = "prompt-set:0.1.0"
$env:FACTORYOPS_AGENT_MODEL_POLICY_VERSION = "model-policy:0.1.0"
$env:FACTORYOPS_AGENT_TOOL_POLICY_VERSION = "tool-policy:0.1.0"
$env:FACTORYOPS_AGENT_CONTEXT_POLICY_VERSION = "context-policy:0.1.0"
$env:FACTORYOPS_AGENT_CODE_REVISION = "651228b9d71ee81e80e6a5030e4c49a50ec60f88"
factoryops-agent-ingress
```

七个 Agent 版本字段会在 Kafka Consumer 创建前一次性读取并校验；进程运行期间不会因环境变化而改变当前 Provenance。启动时会应用当前版本化 SQL migration。Consumer Group 固定为 `factoryops-agent-event-ingress-v1`，自动 offset commit 与自动 offset store 均关闭。

## Inbox 到 Run 的可靠调用链

```text
Kafka record
→ Contract decode
→ Inbox transaction commit
→ original Run + initial history transaction commit
→ synchronous Kafka offset commit
```

Inbox 和 Run 故意使用两个顺序事务。两者之间失败时 offset 仍未提交，Kafka 重投会得到 `duplicate-identical` Inbox outcome，并再次确保 Run；Run 自身由 `trigger_event_id` 唯一约束保证幂等。Run 已创建而 offset commit 失败时，重投返回 `already-started`，不会改写原 Provenance。

数据库或 Kafka adapter 故障会 seek 当前 record 并由进程循环重试。持久化 Run 与事件 Incident 不一致、Run Contract 损坏等完整性故障会终止进程，避免无限重试错误数据。非法事件会被拒绝且不创建 Run。

## Run 生命周期持久化

内部 `AgentRunLifecycleService` 提供 original/replay Run 创建、读取和状态迁移。`agent_runs` 保存当前快照，`agent_run_transitions` 保存不可追加后修改的迁移历史；两者在同一个 MySQL 事务内更新。迁移使用 `expected_status + expected_revision` 乐观锁，重复请求由 `transition_request_id` 分类为 identical 或 conflicting，不自动重试业务命令。

当前 Kafka 入口只创建 `PENDING` Run。它不会把 Run 迁移到 `RUNNING`，也不会启动 Coordinator、LLM 或 Tool；这些属于后续 Change。

可靠性语义、失败窗口和被放弃的方案见当前 OpenSpec Change 的 `technical-decisions.md`。
