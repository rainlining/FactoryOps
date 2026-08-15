# Review Handoff：2026-08-15-consume-quality-incident-events-idempotently

## 元数据

- `learning_level`: `deep`
- `status`: `review-handoff-ready`
- `branch`: `codex/consume-quality-incident-events-idempotently`
- `worktree`: `C:\Users\小霖\Desktop\work\project2\FactoryOps\.worktrees\consume-quality-incident-events-idempotently`
- `base_commit`: `753c23b34157f7007ef660b6b93a27ca6ae46ea2`
- `implementation_head_before_handoff`: `2b37871bac92d7f94fceaca4498fda851641b2f8`
- Review 时以 feature branch 最新提交为准。

## 已实现范围

- 新建最小 Python `services/agent-service`，只包含 Kafka Event Ingress。
- 冻结 Contract/routing validation、durable Inbox、rejection evidence 和 manual offset 协议。
- 实现 `confluent-kafka` adapter、SQLAlchemy Core 事务和版本化 SQL migration。
- 实现首次接收、相同重投、合法冲突、非法消息和 tombstone 分类。
- 使用真实 Kafka 4.1.0 + MySQL 8.4 验证 DB/offset 失败窗口。

明确不包含：Coordinator、Agent Run、LLM、Prompt、Context、Tool、Redis、DLQ、批量消费或 Java 业务表修改。

## Review 前先读技术取舍

首先阅读 `technical-decisions.md`。它逐项说明 Python ownership、confluent-kafka、MySQL Inbox、SQLAlchemy Core、逐条同步 commit、seek 恢复、poison message 隔离和 raw/canonical 双表示的选择与放弃理由。

## 建议 Code Walkthrough 顺序

1. `event_ingress/main.py`：进程入口、固定 Group ID、关闭 auto commit/store。
2. `kafka_adapter.py`：poll record、同步提交 `offset + 1` 和 seek。
3. `worker.py`：处理后提交、任一失败 seek、结构化日志。
4. `decoder.py`：UTF-8/JSON/Contract/key validation 和 canonical hash。
5. `processor.py`：invalid 与 valid 分流。
6. `repository.py`：Inbox transaction、identical/conflicting 与 rejection。
7. `migrations/001_create_agent_event_inbox.sql`：主键、Kafka 来源唯一键和不保存非法 raw payload 的表边界。
8. `test_kafka_mysql_e2e.py`：DB 已提交、offset commit 失败、seek、重投、最终 commit 的真实证据。

## 真实调用链

成功：Kafka poll → `KafkaRecordDecoder.decode` → `MySqlInboxRepository.accept` → MySQL COMMIT → `ConfluentKafkaConsumer.commit(offset + 1)` → success log。

相同重投：poll → decode/canonical hash → Inbox 主键已存在且 hash 相同 → `duplicate-identical` → commit 当前重复 offset。

非法消息：poll → decode failure → `repository.reject` 持久化来源/hash/reason → commit offset，避免 poison loop。

瞬时失败：DB 或 offset commit 抛错 → `worker._seek_for_retry(current offset)` → 不处理更高 offset → 下次重投。

## 验证与风险

完整证据见 `verification.md`：Agent Service 9、Contract 35、Java unit 27、Java integration 38 全部通过，Ruff 与 diff 检查通过。

主要剩余风险：串行吞吐有限；无 backoff/DLQ；线性 migration runner 只服务当前两张表；未建立 Coordinator 消费 Inbox 的 ownership。

## Owner 修改与故障实验

Owner 修改：为成功日志增加 `redelivery=true/false`，仅 `duplicate-identical` 为 true，不改表结构，并增加日志断言。

Failure/debug exercise：复现 Inbox 已提交但首次 offset commit 失败，观察 committed offset 未推进、seek 当前 offset、第二次 identical、Inbox count=1 和第二次 commit 成功。自动化基线为 `test_db_commit_before_offset_failure_redelivers_as_identical_duplicate`。

Learning Gate 未完成，不得归档或合并 `main`。

## Review 会话恢复

```powershell
cd C:\Users\小霖\Desktop\work\project2\FactoryOps\.worktrees\consume-quality-incident-events-idempotently
git status --short
git branch --show-current
git log --oneline 753c23b..HEAD
```

Review 会话接手后，实现会话不得并发修改此 worktree。
