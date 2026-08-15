# FactoryOps Agent Service

当前实现可靠的 Kafka Event Ingress，以及尚未接入生产入口的 Agent Run 生命周期持久化。不包含 Coordinator、Agent 执行、LLM、Tool 或 HTTP API。

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
factoryops-agent-ingress
```

启动时会应用当前版本化 SQL migration。Consumer Group 固定为 `factoryops-agent-event-ingress-v1`，自动 offset commit 与自动 offset store 均关闭。

## Run 生命周期持久化

内部 `AgentRunLifecycleService` 提供 original/replay Run 创建、读取和状态迁移。`agent_runs` 保存当前快照，`agent_run_transitions` 保存不可追加后修改的迁移历史；两者在同一个 MySQL 事务内更新。迁移使用 `expected_status + expected_revision` 乐观锁，重复请求由 `transition_request_id` 分类为 identical 或 conflicting，不自动重试业务命令。

该能力目前没有 Kafka 或 HTTP 入口。它只为后续 Coordinator/Worker Change 提供可靠的持久化边界。

可靠性语义、失败窗口和被放弃的方案见当前 OpenSpec Change 的 `technical-decisions.md`。
