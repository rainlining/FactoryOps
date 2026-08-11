# Change 提案：2026-08-10-define-vision-inspection-contract

## 元数据

- `change_id`: `2026-08-10-define-vision-inspection-contract`
- `status`: `applying-stage-3`
- `stage_1_review`: `accepted`
- `stage_2_review`: `accepted`
- `next_transition`: `applying-stage-3（需项目所有者批准 Stage 3 后）`
- `learning_level`: `deep`
- `first_deep_reference`: `N/A`
- `depends_on`: `[2026-08-10-establish-openspec-learning-governance]`
- `spec_refs`: `[vision-inspection-contract, development-governance]`

## 为什么现在做

后续 `define-evaluation-scenario-contract`、Java Inspection Intake、Kafka anomaly event 和真实 Vision Service 都需要表达同一个事实：视觉质检系统对一张工业图像产生了什么结果。

如果这些能力各自临时定义 `anomaly_score`、模型版本和 Artifact 字段，会形成多个不兼容的数据形状，也会让 fake/recorded result 与未来真实 Vision Service 的输出不一致。因此，先冻结跨服务 Contract，再让后续能力依赖它。

## 范围

本 Change 的唯一核心能力是定义视觉质检结果与业务系统之间的版本化 Contract。

包含：

- Contract envelope 和 `contract_version`；
- `inspection_id` 与不可变 `result_id` 的双重身份；
- Inspection、输入图像、原始生产者、模型和时间信息；
- `is_anomaly`、`anomaly_score`、`decision_threshold` 的语义与约束；
- 可选定位 Artifact 引用；
- fake 与 vision-service 两类原始来源；
- recorded 作为外层 Evaluation/Replay/Event 传递上下文，不改写结果本身；
- 精确版本支持和未知字段拒绝规则；
- 重复结果与冲突结果的 Contract 语义；
- 有效、无效、fake 和 recorded 示例；
- Contract validation 和 compatibility test 设计。

## 非目标

- 不实现 MVTec AD 2 模型、训练、推理或 Vision Service API；
- 不下载或整理 Sheet Metal 数据集；
- 不定义图像上传流程或 MinIO 部署；
- 不定义 Kafka Event envelope 或 Topic；
- 不创建 Java Inspection 领域模型、数据库表或事务；
- 不定义业务严重程度、处置动作或 Agent recommendation；
- 不实现 Evaluation Scenario、Cost Model 或 Evaluator；
- 不要求不同模型版本的 anomaly score 可直接横向比较。

## 预期影响

- 新增生效前规格：`vision-inspection-contract`；
- 后续实现阶段预计新增机器可校验 Schema、fixtures 和 contract tests；
- 不修改任何运行时服务，因为当前尚无运行时工程。

## 依赖与后续关系

- 已完成依赖：开发治理与 Learning Gate；
- 直接服务于：`define-evaluation-scenario-contract`；
- 后续被依赖：Inspection Intake、Vision Service、相关 Kafka Event 和 Agent Context；
- 真实 Vision Service 必须遵守本 Contract，但其内部模型可以独立演进。

## 学习等级理由

本 Change 是项目第一次正式设计跨服务版本化 Contract，涉及字段语义、兼容演进、生产者与消费者解耦、重复与冲突输入等关键工程问题，因此为 `deep`。

后续 API/Event/Agent Contract 不能仅因都使用 JSON 就自动降级；只有当版本、兼容和失败语义相同，且没有新的并发或交付模型时，才可引用本 Change 评估 `standard` 或 `delegated`。

## 验收摘要

- 技术验收：Schema 能拒绝非法结果、接受真实/fake/recorded 合法结果，并用测试证明兼容规则；
- 学习验收：项目所有者能够解释字段语义、版本策略和失败边界，定位 Schema 与测试，亲自补充一个非法 fixture，并完成冲突结果调试实验。
