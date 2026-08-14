# Quality Incident Opened Event Contract

该目录冻结 Java Business World 向 Agent World 发布的首个业务事件：
`quality.incident.opened`。事件只说明一个 `OPEN` Quality Incident 已经在
Java 事务中成立；它不要求 Consumer 再创建 Incident。

## v1.0 文件

- `v1.0/schema.json`：严格 JSON Schema，禁止未知字段。
- `v1.0/routing.json`：Kafka topic、message key 路径和编码约定。
- `fixtures/valid/incident-opened.json`：有效事件样例。
- `fixtures/invalid/`：稳定的拒绝样例。
- `validator.py`：Schema 校验、跨字段语义校验、canonical form 和关系分类。

## 稳定身份

事件 ID 使用以下确定性规则：

```text
EVT- + UPPER_HEX(SHA-256(
  "factoryops:event:quality.incident.opened:v1:" + incident_id
))
```

同一 Incident 的首次发布、Producer retry、Outbox replay 和 Kafka redelivery
必须使用相同的 `event_id`、`occurred_at` 与 canonical payload。不能在重试时
读取当前数据库状态并重建事件。

## Kafka 路由

- Topic：`factoryops.quality.incident.v1`
- Message key：`payload.incident_id`
- Value：UTF-8 JSON，必须先通过本 Contract 校验

路由文件只冻结通信约定。本 Change 不创建 topic，也不实现 Producer、Consumer
或 Outbox。

## 本地验证

在仓库根目录执行：

```powershell
python -m unittest discover `
  -s contracts\quality_incident_opened\tests `
  -t . `
  -v
```
