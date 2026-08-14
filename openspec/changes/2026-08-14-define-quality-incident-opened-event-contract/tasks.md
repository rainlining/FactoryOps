# Change 任务：2026-08-14-define-quality-incident-opened-event-contract

## 设计

- [x] 完成自主技术取舍与 OpenSpec 设计。
- [x] 项目所有者 review 技术文档。

## 实现

- [x] JSON Schema 与 valid fixture。
- [x] invalid fixtures 与语义 Validator。
- [x] canonical relation classifier 与测试。
- [x] 文档、格式、diff 和 dataset scope 验证。

## Handoff

- [x] 填写 verification 和 review-handoff，推送并停在 review-handoff-ready。
- [ ] 独立 Review 会话完成 Standard Learning Gate。

## 实施计划

### Task 1：冻结 Schema 与有效样例

- 先用测试声明 v1.0 Schema、稳定 event_id、固定事件类型、OPEN 状态和 UTC 时间格式。
- 确认测试因 Contract 包尚不存在而失败。
- 增加 `v1.0/schema.json`、包入口和有效 fixture，使 Schema 与身份测试通过。

### Task 2：实现语义 Validator 与无效样例

- 先覆盖不支持版本、未知字段、身份不一致、关联字段不一致和非 UTC 时间。
- 实现统一的结构化错误、Schema 路径定位和跨字段语义校验。
- 用 invalid fixtures 固化每条失败边界。

### Task 3：实现 canonical relation classifier

- 先测试 key 顺序不影响 canonical form，以及 identical、conflicting、distinct 三种关系。
- 验证非法事件在关系分类前被拒绝。
- 实现 canonical bytes 与关系分类，不引入 Kafka 运行时代码。

### Task 4：文档、回归与 handoff

- 补齐 Contract README、验证证据、任务状态和独立 Review 路线。
- 执行新 Contract 测试、Vision Contract 回归、仓库相关回归与 `git diff --check`。
- 检查 `dataset/` 未被修改，提交、推送并停在 `review-handoff-ready`。
