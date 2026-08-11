# Change 学习预讲解：2026-08-10-define-vision-inspection-contract

## 学习元数据

- `learning_level`: `deep`
- `pattern_stage`: `first-deep`
- `first_deep_reference`: `N/A`
- `preflight_status`: `passed`
- `gate_status`: `in-progress`

## 这次真正需要学会什么

本 Change 不要求背诵 JSON Schema 关键字。真正目标是能够：

1. 区分内部数据类型和跨服务 Contract；
2. 解释为什么 Contract 必须先于 Producer/Consumer 实现；
3. 判断字段是感知事实、provenance、业务决策还是 Evaluation ground truth；
4. 解释 major/minor 版本变更的兼容边界；
5. 解释为什么 `is_anomaly`、score 和 threshold 不能相互矛盾；
6. 解释为什么 score 不是跨模型可比较的业务置信度；
7. 区分 inspection identity 与不可变 result identity；
8. 区分原始来源与本次传递方式；
9. 区分相同重放和相同 result identity 下的冲突结果；
10. 根据 validation error 定位 Contract 或 fixture 中的具体错误。

## 核心概念预讲解

### Contract 是边界承诺

Contract 不是某个 Python class 的导出结果。它是 Producer 和多个 Consumer 对字段、约束、版本和失败行为的共同承诺。未来 Vision 内部可以更换模型框架，只要输出仍符合 Contract，业务侧不应被迫重写。

### 结构正确不等于业务真实

Schema 能判断 `0.93` 是否在 `[0,1]`，不能判断图像是否真的异常。前者是 Contract validation，后者属于 Vision benchmark 和 dataset ground truth。二者混在一起会造成错误的责任边界。

### Ground truth 必须隔离

Evaluation 可以知道图片真实标签，但业务系统和 Agent 只能看到模拟真实生产环境可获得的 inspection result。把 ground truth 放进 payload 会造成答案泄漏，使 Benchmark 失真。

### 版本不是装饰字段

如果改变 score 范围、删除 required 字段或改变阈值判断，却不提升 major version，旧 Consumer 会按旧语义错误解释新数据。这比直接报错更危险。

### 业务质检与结果身份不同

`inspection_id` 关联一次业务质检，`result_id` 标识一份不可变结果。同一质检可以有多份结果；相同 result identity 才能用于判断重放或内容冲突。

### 原始来源与传递方式不同

`vision-service` 或 `fake` 回答“谁产生了结果”；`recorded` 回答“这次如何传递结果”。后者不能改写不可变 Vision Result，应由外层 Evaluation/Replay/Event 上下文表达。

### 重放与冲突不同

完全相同的结果可能来自网络重试或 Kafka at-least-once；它应被安全识别。相同 identity 下出现不同业务内容则意味着数据污染、Producer bug 或身份设计错误，不能简单“最后写入覆盖”。

## 与已完成内容的依赖

- 使用已归档治理 Change 定义的 Deep Change 预讲解、分阶段 apply、真实 Walkthrough 和 Learning Gate；
- 当前没有业务代码，因此 Contract 可以在不迁移运行时的情况下先冻结；
- 本 Change 完成后，Evaluation Scenario 和 Java Inspection Intake 才有稳定的视觉结果依赖。

## 编码前需要能够回答的问题

- 哪些字段属于 Vision 事实，哪些字段绝不能由 Vision producer 决定？
- 为什么 threshold 应随结果或明确策略版本一起被记录？
- 为什么 `score=0.93` 不能自动表示业务风险为 HIGH？
- 为什么 minor version 仍需要 Consumer 明确列入支持列表？
- 相同 result identity 的完全相同结果与不同 score 各应如何处理？
- 为什么相同 inspection 下不同 result identity 不自动构成冲突？
- 为什么 recorded 不应改写 Vision Result 的 origin？
- fake fixture 如何做到与未来真实 Producer 共用 Contract，又不伪装成真实推理？

## 未来真实 Code Walkthrough 路线

当前尚未编码。Apply 后 Walkthrough 必须使用实际文件和符号覆盖：

1. Schema 入口；
2. 基本字段校验；
3. score/threshold 跨字段校验；
4. version compatibility 判断；
5. fake/vision fixtures 与 recorded 外层示例；
6. 失败测试及错误路径。

## 项目所有者亲自修改任务

在 Stage 3 由项目所有者新增一个 `anomaly_score = 1.01` 的非法 fixture，并补充或调整测试，使其验证：

- fixture 被拒绝；
- 错误能定位到 `anomaly_score`；
- 合法边界值 `1.0` 仍被接受。

该任务不承担生产安全控制，但要求理解数值边界与负向 Contract Test。

## Failure/Debug Exercise

在 Stage 3 构造以下冲突结果：

```text
anomaly_score = 0.93
decision_threshold = 0.60
is_anomaly = false
```

预期：跨字段校验拒绝输入，而不是自动修正 boolean 或静默接受。

需要观察：

- 哪个 validator 报错；
- 错误路径和错误代码；
- 结果是否在进入任何业务 Consumer 前停止；
- 把判断从 `>=` 错改为 `>` 后，等于 threshold 的边界测试如何暴露问题。

清理方式：删除或恢复故障 fixture，恢复正确比较逻辑，重新运行全部 Contract Tests。

## Learning Gate

- [ ] 能解释 Contract 边界和字段分类。
- [ ] 能解释 version compatibility 规则。
- [ ] 能沿真实校验调用链定位代码。
- [ ] 能解释至少一个 validation failure path。
- [x] 已完成非法 score fixture 修改任务。
- [x] 已完成 boolean/threshold 冲突实验。
- [ ] 已 review 最终 diff 并明确接受。

当前只完成学习预讲解材料，尚未通过 Learning Gate，也未获编码批准。

## 所有者实践记录

2026-08-11，项目所有者亲自完成：

- 创建 `anomaly-score-out-of-range.json`，并保持除 `anomaly_score = 1.01` 外与合法 fake fixture 一致；
- 添加 `1.01` 被拒绝且 path 为 `$.observation.anomaly_score` 的负向测试；
- 添加合法上边界 `1.0` 的正向测试，并使 `is_anomaly = true` 保持跨字段一致；
- 临时把 `score >= threshold` 改为 `score > threshold`；
- 观察 threshold equality test 从 PASS 变为 ERROR，并沿堆栈定位到 `validate_result`；
- 恢复 `>=` 后运行完整测试，17 项全部通过。

尚未完成：最终真实 Code Walkthrough review、剩余解释确认和最终 diff 接受。

## Learning Preflight 通过记录

2026-08-11，项目所有者通过三个实际场景完成编码前理解确认：

- 能区分相同 `inspection_id` 下的不同 `result_id`，并说明它们不自动构成冲突；
- 能区分 `duplicate-identical` 与相同 `result_id`、不同内容的 `duplicate-conflicting`；
- 能说明 `origin.kind = vision-service` 与外层 `input_mode = recorded` 的职责差异；
- 能判断只明确支持 1.0 的严格 Consumer 必须拒绝 1.1；
- 理解 Consumer 只有在增加 1.1 Schema/兼容确认并把 1.1 加入明确支持列表后，才能合法接收该版本。

该记录只表示编码前心智模型通过，不表示最终 Learning Gate 已完成。
