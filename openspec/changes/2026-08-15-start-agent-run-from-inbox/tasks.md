# Change 任务：2026-08-15-start-agent-run-from-inbox

## 设计

- [x] 批准同步 Consumer 编排、配置、失败和可观测性设计。
- [x] 编写 OpenSpec 与中文技术设计。

## 实现

- [x] Task 1：以测试冻结配置加载与 DecodedEvent Incident 语义。
- [x] Task 2：实现 IncidentRunStarter 的 created/already-started/integrity 行为。
- [x] Task 3：将 Starter 接入 Processor 并扩展 ProcessingResult。
- [x] Task 4：在 Worker/main 区分 retryable 与 fatal 失败。
- [x] Task 5：完成 MySQL 与 Kafka 崩溃恢复、并发和回归测试。
- [x] Task 6：完成 verification、独立审查和 review handoff。

## Handoff

- [ ] 推送 feature branch并进入 `review-handoff-ready`（GitHub 网络恢复后执行）。
- [ ] 独立 Review/Learning 会话完成 Deep Learning Gate。
