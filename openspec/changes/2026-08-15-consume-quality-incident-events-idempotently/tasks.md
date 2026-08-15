# Change 任务：2026-08-15-consume-quality-incident-events-idempotently

## 设计

- [x] 冻结 Agent Event Ingress 边界、失败顺序和技术选型。
- [x] 项目所有者授权 Codex 自行完成本 Change 的技术取舍并连续实现。
- [x] 完成 Deep Change learning preflight 文档。

## 实现

- [ ] 建立最小 Python Agent Service 包、配置和 migration runner。
- [ ] 以测试定义 decoder、Inbox outcome 和 Worker commit/seek 协议。
- [ ] 实现 MySQL Inbox 与 rejection 事务。
- [ ] 实现 confluent-kafka adapter 和串行 Worker。
- [ ] 增加真实 MySQL 与 Kafka 端到端故障测试。
- [ ] 执行完整验证、格式检查和 dataset scope 检查。

## Handoff

- [ ] 填写 verification 与 review-handoff 并推送 feature branch。
- [ ] 独立 Review/Learning 会话完成 owner 修改、故障实验和 Deep Learning Gate。
