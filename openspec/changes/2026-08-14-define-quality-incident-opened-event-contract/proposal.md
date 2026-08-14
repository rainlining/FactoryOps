# Change 提案：2026-08-14-define-quality-incident-opened-event-contract

## 元数据

- `change_id`: `2026-08-14-define-quality-incident-opened-event-contract`
- `status`: `completed`
- `learning_level`: `standard`
- `first_deep_reference`: `2026-08-10-define-vision-inspection-contract`
- `depends_on`: `[2026-08-13-establish-quality-incident]`
- `spec_refs`: `[quality-incident, vision-inspection-contract]`
- `implementation_session`: `current Codex task`
- `review_session`: `completed`

## 为什么要做

Quality Incident 已经成为 Java Business World 中成立的业务事实，但 Agent World 尚无稳定、版本化的事件边界。若直接实现 Outbox、Producer 和 Consumer，事件语义、Kafka 路由与可靠性机制会在同一个 Change 中相互纠缠，难以独立 review 和演进。

## 范围

- 冻结首个业务事件 `quality.incident.opened` 的 v1.0 JSON Contract。
- 冻结事件身份、业务时间、证据引用、生产者信息和 Kafka 路由约定。
- 提供 JSON Schema、有效/无效 fixture、Contract Validator 与 relation classifier。
- 明确 retry/replay 时相同业务事实必须产生相同事件身份和内容。

## 非目标

- Outbox 表、Java Producer、Kafka broker、topic 创建、Consumer、offset 或 retry。
- Agent Runtime、Coordinator Run、Incident 状态迁移、Batch HOLD。
- 发布 `quality.anomaly_detected` 或其他事件。

## 预期影响

- 新增规格：`quality-incident-opened-event-contract`。
- 新增 `contracts/quality_incident_opened/v1.0/schema.json`、fixtures 和 Python 验证测试。
- 后续 Outbox Change 必须逐字复用该 payload 与身份规则，不得重新发明 Contract。

## 依赖与顺序

- 前置：Quality Incident 已能原子创建并具有稳定 ID。
- 后续：`persist-quality-incident-outbox` → `publish-outbox-events-to-kafka` → `consume-quality-incident-events-idempotently`。

## 学习等级理由

本 Change 复用 Vision Contract 首次 deep 学到的 JSON Schema、严格字段、fixture 与 relation test 模式，因此降为 `standard`。新增内容是业务事件 envelope、Kafka 路由和演进规则，但不引入事务、并发或运行时失败模型；Outbox 与 Kafka Producer/Consumer 将分别保持 deep。

## 验收摘要

- 技术验收：Schema、语义验证、有效/无效 fixtures、canonical relation 和文档一致性通过。
- 学习验收：项目所有者理解事件代表的事实、字段所有权、稳定身份、路由与版本演进，并完成 diff review。
