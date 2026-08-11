# Change 设计：2026-08-10-define-vision-inspection-contract

## 设计目标

定义一个与具体模型实现、消息系统和业务数据库解耦的版本化视觉质检结果。相同 Contract 同时供 fake fixture、保持原始 payload 的 recorded replay 和未来真实 Vision Service 使用。

本 Change 冻结的是“跨边界可观察结果”，不是 Vision Service 的内部 Python 类型，也不是 Kafka Event envelope。

## 为什么现在应该做

它位于三个后续方向的共同上游：

```text
Vision Inspection Contract
├── Evaluation Scenario 中的可见 inspection observation
├── Java Inspection Intake 的输入边界
└── 未来真实 Vision Service 的输出边界
```

如果先做 Scenario 或 Java Intake，就必须在这些 Change 中临时发明视觉字段。先建立本 Contract 可以降低返工，并允许没有真实模型时继续开发确定性后端和 Evaluation。

## Contract 边界

### Contract 拥有

- 一次 inspection result 的稳定身份；
- 图像 Artifact 引用；
- 原始结果来源；
- 模型与 producer provenance；
- image-level anomaly observation；
- 可选定位 Artifact；
- 版本和兼容语义。

### Contract 不拥有

- Order、Batch、Customer 等业务上下文；
- 缺陷严重程度和质量策略；
- PASS、RECHECK、HOLD_BATCH 等业务动作；
- Dataset ground truth；
- Kafka key、partition、offset 或 delivery semantics；
- recorded、replay 等本次传递方式；
- 数据库幂等实现；
- Agent Context 和 Prompt。

## 建议的逻辑结构

最终字段名将在 apply 阶段通过 executable schema 和 fixtures 验证。目标逻辑结构如下：

```json
{
  "contract_version": "1.0",
  "inspection_id": "inspection-00731",
  "result_id": "result-1001",
  "input": {
    "image_uri": "artifact://images/sheet-metal-00731",
    "sha256": "<64 lowercase hex characters>"
  },
  "origin": {
    "kind": "vision-service",
    "producer_name": "factoryops-vision",
    "producer_version": "0.1.0"
  },
  "model": {
    "name": "sheet-metal-anomaly-detector",
    "version": "vision-v1"
  },
  "observation": {
    "is_anomaly": true,
    "anomaly_score": 0.93,
    "decision_threshold": 0.60
  },
  "artifacts": {
    "defect_mask": {
      "uri": "artifact://masks/00731",
      "media_type": "image/png"
    }
  },
  "timing": {
    "produced_at": "2026-08-10T10:00:00Z",
    "inference_ms": 37
  }
}
```

设计阶段示例不是已实现 Schema；apply 时必须通过测试确认最终字段、required/optional 集合和严格校验行为。

## 关键语义与不变量

### 结果身份

`inspection_id` 标识一次业务质检；`result_id` 标识该质检下产生的一份不可变视觉结果。一个 inspection 可以关联多份结果，例如正式重检、不同模型运行或 Evaluation Replay。

相同 `result_id` 必须始终表示相同语义内容。结果是否被业务采用不由本 Contract 决定，而由后续 Java Inspection 领域规则决定。

### 原始来源与传递方式

`origin.kind` 只表达结果最初由 `vision-service` 还是 `fake` producer 产生。`recorded` 描述本次数据如何进入系统，属于 Evaluation Scenario、Replay Request 或 Event Envelope，不进入不可变 Vision Result。

因此，同一个 `result_id` 从实时传递变为 recorded replay 时，Vision Result payload 不发生变化，避免被误判为内容冲突。

### 异常判断一致性

V1 Contract 采用明确关系：

```text
is_anomaly = anomaly_score >= decision_threshold
```

这样 recorded/fake fixture 无法提供自相矛盾的 boolean 和 score。边界相等时判定为 anomaly，避免不同语言实现使用 `>` 与 `>=` 产生漂移。

### Score 不是业务置信度

`anomaly_score` 是给定模型版本下的感知分数。它不能直接表达业务严重程度，也不保证跨模型版本校准。Quality 领域或 Agent 可以结合策略解释它，但不能把高 score 自动等同于 STOP_LINE。

### Artifact 引用

图像和 mask 使用 URI 引用，不内嵌二进制内容。Contract 不在本 Change 中绑定 MinIO URI，以便 fake fixture 和未来存储实现共享边界。

### Fake 与真实结果保持相同核心形状

所有结果都必须包含 producer 和 model provenance。Fake 使用明确的 fixture producer 与 fixture model，并由 `origin.kind: fake` 标识，不允许通过省略 model 形成 Consumer 特殊分支。

### 严格顶层字段

V1 倾向拒绝未知顶层业务字段，以阻止 Vision producer 偷渡 recommendation 或 ground truth。兼容扩展应通过新 minor version 和明确的可选字段完成。

## 版本策略

- `major`：删除 required 字段、改变已有字段语义/类型/范围、改变异常判断规则。
- `minor`：表示新增可选字段等非破坏性演进，但不会被旧 Consumer 自动接受。
- Producer 必须声明准确版本；Consumer 必须明确声明支持范围。
- Consumer 只接受明确列出的精确版本；未知 major、未知 minor 和未知字段都 fail closed。

这不是完整 Schema Registry 方案；Registry、发布和兼容检查流水线属于后续工程 Change。

## 预期数据流

开发早期：

```text
fake fixture 或原始 recorded payload
→ 外层上下文按需标记 input_mode=recorded
→ Contract validator（Vision Result 本身不被改写）
→ 后续 Evaluation Scenario 或 Java Inspection Intake
```

真实 Vision Service 完成后：

```text
Sheet Metal image reference
→ Vision Service
→ Vision Inspection Contract payload
→ Contract validator
→ Java Inspection Intake
→ 后续业务事务与事件链
```

验证器只确认结构和跨字段不变量，不负责判断图像是否真的有缺陷，也不负责业务动作。

## 状态与重复语义

本 Change 不建立数据库状态机，但定义 Consumer 未来必须能区分的三种输入状态：

```text
new
→ 第一次看到该 result identity

duplicate-identical
→ 相同 result_id 和相同规范化语义内容的重放

duplicate-conflicting
→ 相同 result_id，但规范化语义内容不同
```

相同 `inspection_id`、不同 `result_id` 是多份独立结果，不自动构成冲突。`duplicate-identical` 可以被幂等忽略；`duplicate-conflicting` 必须显式失败。持久化、业务权威结果选择、并发竞态和锁不在本 Change 实现，将在 Java/Kafka/Redis Change 中分别学习。

## 失败路径

### Schema 失败

- 缺少 required 字段；
- score/threshold 越界或非有限值；
- 时间、hash、URI 或枚举格式非法；
- 未知顶层字段；
- `is_anomaly` 与 threshold 关系冲突。

预期行为：在进入业务领域前拒绝，返回可定位到字段路径的 validation error。

### 版本失败

- 未声明版本；
- version 格式非法；
- Consumer 不支持该精确 major.minor version。

预期行为：fail closed，不猜测字段含义。

### Provenance 失败

- fake 冒充 vision-service；
- fake 或真实来源缺少 model、producer 或产生时间；
- replay 通过改写 origin 表达 recorded，导致不可变结果变化。

预期行为：拒绝或标记 fixture 无效，不能进入后续基准测试。

### 重复冲突

同一 `result_id` 出现不同 score、threshold、image hash、模型或判断结果。

预期行为：未来 Consumer 报告 conflict，不覆盖旧事实。本 Change 只冻结语义并准备 fixture，不实现并发处理。

### Ground truth 泄漏

Fixture 把 dataset label、required outcome 或标准动作放入 payload。

预期行为：严格 Schema 拒绝这些字段，防止 Evaluation 答案进入业务/Agent 世界。

## 测试策略

### Schema tests

- 最小合法 vision-service result；
- 合法 fake result；
- 合法 recorded replay 保持原始 result payload；
- score 和 threshold 的 0、1、相等边界；
- 缺失、越界、冲突、未知字段和未知 major version。

### Compatibility tests

- 1.0 Consumer 接受合法 1.0；
- 只支持 1.0 的 Consumer 拒绝 1.1；
- 明确支持 1.0 和 1.1 的 Consumer 接受对应精确版本；
- 只支持 1.x 的 Consumer 拒绝 2.0；
- 破坏性 fixture 变化必须触发测试失败。

### Contract fixtures

Fixtures 同时是文档示例和后续 Change 的测试输入。不得只有一份 happy-path JSON。

## 方案比较

### 方案 A：等真实 Vision Service 完成后再定义输出

模型实现会反向决定业务 Contract，导致 Java、Evaluation 和 fake fixture 被具体框架输出绑住。

### 方案 B：只定义 `is_anomaly` 和 `anomaly_score`

字段少，但无法解释 threshold、模型版本、输入图像和结果来源，也难以复现或审计。

### 方案 C：冻结最小但可审计的版本化 Contract

采用该方案。它覆盖身份、感知结果、provenance、Artifact 和兼容规则，同时排除业务决策、Kafka 和存储实现。

## 预计 Apply Stages

预计分为 3 个小阶段，每阶段都在 review 后才开始：

1. **Stage 1 — Executable Schema**：先写合法/非法 contract tests，再实现最小机器可校验 Schema 和跨字段校验。
2. **Stage 2 — Fixtures and Compatibility**：加入 fake、vision-service fixtures、recorded 外层示例、重复/冲突 fixtures，以及精确版本 compatibility tests。
3. **Stage 3 — Learning and Hardening**：完成所有者非法 fixture 修改任务、冲突结果 failure/debug exercise、真实文件 Walkthrough 和最终验证。

三个阶段都不创建 Vision Service、Java Service、Kafka 或数据库。
