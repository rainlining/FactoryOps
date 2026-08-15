# 学习计划：2026-08-15-consume-quality-incident-events-idempotently

## 元数据

- `learning_level`: `deep`
- `gate_status`: `preflight-passed`

## Review 时应理解

- Consumer Group、Partition owner、poll position 与 committed offset 的区别。
- 为什么提交的是 `offset + 1`。
- 为什么“不 auto commit”仍不足以避免当前进程越过失败消息。
- Inbox 如何把 DB commit → offset commit 之间的崩溃窗口转化为 identical duplicate。
- invalid、duplicate-identical 和 duplicate-conflicting 为什么采用不同处理。
- 为什么 Redis SETNX 不是当前 durable idempotency 的事实来源。

## Owner 修改任务

在不改变表结构的前提下，为结构化成功日志增加 `redelivery=true/false`：只有 outcome 为 `duplicate-identical` 时为 true，并增加日志测试。

## Failure/Debug Exercise

- 注入：MySQL Inbox 已提交后，让第一次 Kafka offset commit 失败。
- 预期：Worker seek 当前 offset；Kafka committed offset 未前进；再次处理得到 `duplicate-identical`，Inbox 仍只有一行；第二次 commit 成功。
- 观察：Kafka committed offset、Consumer position、Inbox count、两次 outcome 和日志。
- 复位：移除 commit failure adapter，重新运行测试或 Worker。
- 完成后应能解释：为什么 Producer idempotence 与 Consumer Inbox 分别解决不同重复窗口。

## Learning Gate

- [ ] 能沿 poll → validate → DB transaction → commit offset 定位真实代码。
- [ ] 能解释一条 invalid 与一条 transient failure 路径。
- [ ] 完成 Owner 修改。
- [ ] 完成 failure/debug exercise。
- [ ] review 技术选型文档和最终 diff 并明确接受。
