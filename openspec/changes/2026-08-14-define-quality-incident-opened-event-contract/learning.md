# 学习计划：2026-08-14-define-quality-incident-opened-event-contract

## 元数据

- `learning_level`: `standard`
- `pattern_stage`: `standard-after-vision-contract-deep`
- `first_deep_reference`: `2026-08-10-define-vision-inspection-contract`
- `gate_status`: `not-started`

## 需要理解

- 为什么发布 Incident Opened 而不是 Anomaly Detected。
- envelope 与 payload 的字段所有权。
- event_id、Kafka key、correlation_id、causation_id 的区别。
- occurred_at 为什么不能在 retry/replay 时更新。
- Contract validation 为什么先于重复关系分类。
- 严格版本演进如何影响 Producer 和 Consumer。

## Review 路线

技术文档 → JSON Schema → valid fixture → invalid fixtures → validator → relation tests。Standard Change 不要求 owner 修改和完整 failure/debug exercise，但必须完成 Contract diff review 和验证命令 review。

## Learning Gate

- [ ] 能解释事件代表的已成立业务事实。
- [ ] 能解释稳定身份、路由 key 与时间语义。
- [ ] 能指出哪些数据被有意排除以及原因。
- [ ] 能区分 identical duplicate、conflicting duplicate 和 invalid event。
- [ ] 已 review 最终 Contract diff 并接受。
