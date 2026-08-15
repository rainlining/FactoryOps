# FactoryOps Agent Service

当前只实现可靠的 Kafka Event Ingress，不包含 Coordinator、Agent、LLM、Tool 或 HTTP API。

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

可靠性语义、失败窗口和被放弃的方案见当前 OpenSpec Change 的 `technical-decisions.md`。
