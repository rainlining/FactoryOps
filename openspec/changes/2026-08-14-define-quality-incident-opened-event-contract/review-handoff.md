# Review Handoff：2026-08-14-define-quality-incident-opened-event-contract

## 恢复信息

- 学习等级：`standard`
- 分支：`codex/define-quality-incident-opened-event-contract`
- Worktree：`C:\Users\小霖\Desktop\work\project2\FactoryOps\.worktrees\define-quality-incident-opened-event-contract`
- Base commit：`ed7d1ae`
- Implementation head commit：`512d0ae`（本 handoff 另有后续文档提交；恢复时以远端 branch head 为准）
- 实现状态：`review-handoff-ready`
- Review 会话：`pending`
- 禁止实现会话与 Review/Learning 会话并发修改本 Change 或 worktree。

## 已实现范围

- 严格的 `quality.incident.opened` v1.0 JSON Schema 与格式化有效样例。
- 可测试的 Kafka 路由约定：topic 为 `factoryops.quality.incident.v1`，message key 取 `payload.incident_id`。
- 确定性 event_id 派生、Schema 校验、跨字段语义校验和结构化错误路径。
- canonical JSON 与 `duplicate-identical`、`duplicate-conflicting`、`distinct` 关系分类。
- 未声明版本、未知字段、身份冲突、关联冲突、非 UTC 时间、非 OPEN 状态和 ground truth 泄漏的负向覆盖。

## 明确非目标

- 未创建 Outbox 表、Kafka topic、Producer、Consumer、offset、retry 或幂等存储。
- 未修改 Java Domain、事务、Incident 状态或 Batch 状态。
- 未实现 Agent Runtime、Coordinator、Tool 或 Evaluation。

## 修改文件与真实入口

- `contracts/quality_incident_opened/v1.0/schema.json`：事件字段和严格版本边界。
- `contracts/quality_incident_opened/v1.0/routing.json`：Kafka 路由约定。
- `contracts/quality_incident_opened/fixtures/`：一份有效事件和四份稳定无效样例。
- `contracts/quality_incident_opened/validator.py`：`validate_event`、`derive_event_id`、`canonicalize_event`、`classify_event_relation`。
- `contracts/quality_incident_opened/tests/`：Schema、路由、语义失败和关系分类测试。
- `contracts/quality_incident_opened/README.md`：Contract 使用边界与本地命令。

## 建议阅读顺序与调用链

1. `README.md`：先确认事件代表“Incident 已成立”，而不是“模型发现异常”。
2. `fixtures/valid/incident-opened.json`：查看完整 envelope 与 payload。
3. `v1.0/schema.json`：追踪严格字段、OPEN、事件类型和 UTC 时间边界。
4. `v1.0/routing.json`：确认 topic 与 message key 不属于 payload 业务事实。
5. `validator.py#validate_event`：先版本和 Schema，再检查事件身份及引用一致性。
6. `validator.py#classify_event_relation`：两个输入都先 canonicalize/validate，再分类。
7. `tests/test_validator.py`：将每条成功/失败路径映射回实现。

成功链：加载 JSON → 检查支持版本 → 加载 v1.0 Schema → 严格 Schema 校验 → event_id/aggregate/correlation/causation 语义校验 → 接受事件。

关系链：分别验证并 canonicalize 两个事件 → event_id 不同为 `distinct` → ID 相同且 bytes 相同为 `duplicate-identical` → ID 相同但 bytes 不同为 `duplicate-conflicting`。

失败链：版本不支持时在加载 Schema 前拒绝；结构非法时返回首个精确 JSON path；结构合法但身份或引用矛盾时返回专用 issue code；任何失败均不产生关系分类。

## 验证证据与限制

- Python Contract 共 35 项通过，其中新 Event Contract 18 项、Vision 回归 17 项。
- Java `mvn test` 共 16 项通过，构建成功。
- `git diff --check` 通过，`dataset/` 未修改或提交。
- 没有执行 Docker/MySQL 集成测试，因为本 Change 不修改 Java 或持久化边界。
- `occurred_at` 与数据库 `QualityIncident.created_at` 的等值映射留给后续 Outbox 集成测试证明。

## Standard Learning Gate

本 Change 不要求 owner 修改或完整 failure/debug exercise。独立 Review 会话需要确认项目所有者能够：

- 解释为何事件选择 Incident Opened，而不是 Anomaly Detected。
- 区分 event_id、Kafka key、correlation_id 与 causation_id。
- 解释 retry/replay 为什么不能更新 event_id、occurred_at 或 canonical payload。
- 指出被有意排除的数据及原因。
- 沿 `validate_event` 和 `classify_event_relation` 定位成功与失败路径。
- review 最终 Contract diff 并明确接受或提出修改。

Review 会话完成前，不得归档该 Change 或合并 `main`。
