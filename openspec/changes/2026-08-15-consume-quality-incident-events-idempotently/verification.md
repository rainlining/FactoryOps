# 验证记录：2026-08-15-consume-quality-incident-events-idempotently

- `status`: `review-handoff-ready`
- `dataset_scope`: `untouched`
- `implementation_verification`: `passed`

## 实际命令与结果

1. `cd services/agent-service && python -m ruff check .`
   - 结果：通过，0 error。
2. `cd services/agent-service && python -m ruff format --check .`
   - 结果：17 个 Python 文件格式正确。
3. `cd services/agent-service && python -m pytest -q`
   - 结果：9 个测试通过。
   - 真实启动 Apache Kafka 4.1.0 与 MySQL 8.4。
4. `python -m unittest discover -s contracts -t . -v`
   - 结果：35 个 Contract 测试通过。
5. `cd backend/business-service && mvn verify`
   - 结果：27 个 Java 单元测试与 38 个集成测试通过，BUILD SUCCESS。
6. `git diff --check`
   - 结果：通过。

## 关键证据

- valid event 首次写入一条 Inbox；不同 JSON 空白的同事件分类为 `duplicate-identical`，不增加 Inbox。
- 同 `event_id`、不同合法 canonical content 分类为 `duplicate-conflicting`，不覆盖 Inbox并增加 rejection。
- invalid UTF-8 与 Kafka tombstone 被确定性拒绝；rejection 只保存 SHA-256 和原因，不保存原始非法 payload。
- Kafka message key 必须等于 `payload.incident_id`。
- Worker 只在 Processor 成功后同步提交 `offset + 1`。
- 数据库处理或 offset commit 失败后，Worker seek 回当前 offset。
- 真实端到端测试证明：Inbox commit 成功、offset commit 失败后，broker offset 未推进；重投分类为 identical，Inbox 仍为一行，第二次 commit 后 offset 才推进。

## 已知限制

- 当前串行逐条消费，未实现 batch、pause/resume、retry backoff 或并发 Worker。
- 当前没有 Coordinator/Agent Run，因此 Inbox 只是可靠入口事实。
- migration runner 只支持当前线性 SQL migration；完整 Alembic 生命周期留给表模型扩大后的独立 Change。
- 没有 DLQ Topic；确定性非法消息只写 MySQL rejection evidence。
- 同一 Group 的多实例由 Kafka 分配 Partition，但本 Change 未实现跨 Partition 的全局调度或 Agent Run ownership。
