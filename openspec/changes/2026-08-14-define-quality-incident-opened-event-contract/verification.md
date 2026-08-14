# 验证记录：2026-08-14-define-quality-incident-opened-event-contract

- `status`: `technically-verified`
- `verified_at`: `2026-08-14`
- `verified_by`: `Codex`

## 实际验证

- `python -m unittest discover -s contracts -t . -v`：通过；新 Event Contract 18 项、既有 Vision Contract 17 项，共 35 项，0 failure、0 error。
- `mvn test`（`backend/business-service`）：通过；Java 单元测试 16 项，0 failure、0 error，构建成功。
- TDD RED 证据：Schema 测试先因 `v1.0/schema.json` 不存在而失败；路由测试先因 `v1.0/routing.json` 不存在而失败；Validator 测试先因模块不存在而失败，补入最小实现后转绿。
- `git diff --check ed7d1ae...HEAD`：通过。
- Change diff 路径检查：仅包含当前 OpenSpec 工件与 `contracts/quality_incident_opened/`；未修改或提交 `dataset/`。

## 已验证边界

- v1.0 严格 Schema 接受有效 fixture，并拒绝未知字段、非 UTC 时间、非 OPEN 状态和未声明版本。
- 稳定 event_id 按 Incident ID 派生；aggregate、correlation 与 causation 的跨字段引用保持一致。
- Kafka topic 与 Incident message key 已由可测试的 `routing.json` 冻结。
- canonical JSON 不受对象 key 顺序影响；关系分类覆盖 `duplicate-identical`、`duplicate-conflicting`、`distinct`，非法事件先拒绝且不分类。

## 限制

- 本 Change 只定义 Contract，没有 Outbox、Kafka broker、Producer、Consumer、offset 或幂等存储，因此不声称已经验证消息发布可靠性。
- `occurred_at = QualityIncident.created_at` 是 Producer 必须遵守的语义；单独的 JSON Validator 无法访问数据库进行比对，后续 Outbox 集成测试必须验证该映射。
- Java 回归使用 `mvn test`，未运行需要 Docker/MySQL 的 Failsafe 集成测试；本 Change 未修改 Java 或数据库代码。

## 状态

- 技术验收：`passed`
- Review Handoff：`push-pending`（GitHub HTTPS 连接连续三次 reset/timeout）
- Standard Learning Gate：`not-started`
- Change：`technically-verified`
