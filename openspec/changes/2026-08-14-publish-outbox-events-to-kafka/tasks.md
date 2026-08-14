# Change 任务：2026-08-14-publish-outbox-events-to-kafka

## 设计与学习预检

- [x] 完成运行形态、单实例、ack、事务、失败、测试和 Learning Lab 讨论。
- [x] 项目所有者 review 并接受书面 OpenSpec 设计。
- [x] 完成 Deep Change 编码前讲解并通过 learning preflight。

## 实现

- [x] 以失败测试定义 Publisher 编排与 Kafka sender 边界。
- [x] 实现稳定 PENDING 查询和条件 PUBLISHED 更新。
- [x] 接入真实 Kafka Producer 配置与 acknowledgement。
- [x] 实现 fixed-delay Poller、配置开关和结构化日志。
- [x] 增加真实 MySQL + Kafka Testcontainers 集成与故障测试。
- [x] 增加 KRaft Kafka、Topic 初始化、Kafbat UI 和中文 Learning Lab。
- [x] 执行格式化、完整验证、diff 与 dataset scope 检查。

## Handoff

- [x] 填写 verification 与 review-handoff，停在 review-handoff-ready。
- [ ] 推送 feature branch 到 GitHub。
- [ ] 独立 Review/Learning 会话完成 owner 修改、故障实验和 Deep Learning Gate。
