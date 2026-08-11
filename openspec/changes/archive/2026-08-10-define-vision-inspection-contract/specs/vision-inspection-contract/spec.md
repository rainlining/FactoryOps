# Vision Inspection Contract 规格增量

## 新增需求

### Requirement: 业务质检与视觉结果具有独立稳定身份

每个视觉质检结果必须包含非空 `inspection_id`、`result_id` 和 `contract_version`。

`inspection_id` 标识一次业务质检；`result_id` 标识该质检下产生的一份不可变视觉结果；`contract_version` 标识数据结构及字段语义的精确版本。同一个 `inspection_id` 可以关联多个不同的 `result_id`。

#### Scenario: 接收受支持版本的结果

- **Given** Consumer 明确支持 Contract version 1.0
- **And** 结果包含 `inspection_id`、唯一 `result_id` 和 `contract_version: "1.0"`
- **When** Consumer 校验结果
- **Then** 版本检查必须通过

#### Scenario: 接收不受支持的 major version

- **Given** Consumer 只支持 major version 1
- **When** 收到 `contract_version: "2.0"`
- **Then** 必须拒绝该结果
- **And** 不得把未知 major version 当作 version 1 继续处理

### Requirement: 结果标识输入图像和结果来源

结果必须包含输入图像的稳定 Artifact 引用，以及产生该结果的原始来源。`origin.kind` 必须是 `vision-service` 或 `fake`。

#### Scenario: 使用 fake result 开发后端

- **Given** 真实 Vision Service 尚未实现
- **When** 测试发送符合 Contract 的 fake result
- **Then** Consumer 必须能够按相同字段语义校验和读取
- **And** `origin.kind` 必须明确标记为 `fake`

#### Scenario: 使用 recorded result 重放

- **Given** 一个此前保存的合法视觉结果
- **When** 它作为 recorded fixture 被重放
- **Then** Vision Inspection Result payload 必须保持原始 `result_id`、`origin`、模型与输入图像 provenance
- **And** `recorded` 必须由外层 Evaluation Scenario、Replay Request 或 Event Envelope 表达
- **And** 不得通过改写 Vision Result 的 `origin.kind` 表达重放

### Requirement: 异常判断具有明确数值约束

结果必须包含 `is_anomaly`、`anomaly_score` 和 `decision_threshold`。Score 和 threshold 必须是 `[0, 1]` 范围内的有限数值。

`is_anomaly` 必须满足：当 `anomaly_score >= decision_threshold` 时为 `true`，否则为 `false`。

#### Scenario: 合法异常结果

- **Given** `anomaly_score` 为 `0.93`
- **And** `decision_threshold` 为 `0.60`
- **When** `is_anomaly` 为 `true`
- **Then** 结果必须通过一致性校验

#### Scenario: Score 超出范围

- **Given** `anomaly_score` 为 `1.01`
- **When** 校验结果
- **Then** 必须拒绝该结果

#### Scenario: Boolean 与 threshold 冲突

- **Given** `anomaly_score` 为 `0.93`
- **And** `decision_threshold` 为 `0.60`
- **When** `is_anomaly` 为 `false`
- **Then** 必须拒绝该结果并指出异常判断不一致

### Requirement: 所有结果记录模型和生产者 provenance

所有结果都必须记录模型名称、模型版本、结果产生时间、生产者名称和生产者版本。Fake 结果必须使用明确的 fixture producer 和 fixture model，并通过 `origin.kind: "fake"` 表明身份，不得伪装成真实模型结果。

#### Scenario: 真实 Vision Service 产生结果

- **Given** 来源为 `vision-service`
- **When** 结果被校验
- **Then** 模型名称、模型版本、生产者名称、生产者版本和产生时间都必须存在

#### Scenario: Fake result 冒充真实来源

- **Given** 一个由测试 fixture 产生的结果
- **When** 来源被标记为 `vision-service` 但缺少真实模型 provenance
- **Then** 必须拒绝该结果

#### Scenario: Fake result 缺少模型信息

- **Given** 来源为 `fake`
- **When** 结果缺少模型名称或模型版本
- **Then** 必须拒绝该结果
- **And** Consumer 不得为 fake result 使用不同的核心数据形状

### Requirement: 定位信息通过可选 Artifact 引用传递

Contract 可以包含 defect mask 等可选定位 Artifact 的 URI 和媒体类型，但不得把大型二进制内容内嵌在结果中。

#### Scenario: 结果包含 defect mask

- **Given** Vision producer 生成了 defect mask
- **When** 构造结果
- **Then** 必须通过 Artifact URI 引用该 mask
- **And** 必须声明媒体类型
- **And** 不得内嵌 mask 二进制数据

#### Scenario: 没有定位能力

- **Given** 当前模型只提供 image-level anomaly score
- **When** 构造结果
- **Then** 可以省略定位 Artifact
- **And** 结果仍可通过校验

### Requirement: Contract 不携带业务决策和 Evaluation Ground Truth

视觉结果只能表达感知事实及 provenance，不得包含业务处置动作、业务严重程度、Agent recommendation 或 Evaluation ground truth。

#### Scenario: Producer 尝试指定 HOLD_BATCH

- **Given** Vision producer 在结果中加入 `recommended_action: "HOLD_BATCH"`
- **When** 使用严格 Contract 校验
- **Then** 必须拒绝该未知业务字段

#### Scenario: Evaluation 使用异常真值

- **Given** Scenario 同时拥有数据集 ground truth 和视觉模型结果
- **When** 构造传给业务系统的视觉结果
- **Then** ground truth 不得出现在 Vision Inspection Contract payload 中

### Requirement: 版本演进遵守兼容规则

Contract 使用 `major.minor` 版本。破坏性字段或语义变更必须提升 major version；minor version 可以表示新增可选字段等非破坏性演进，但 Consumer 只能接受其明确列出的精确版本。未知 major、未知 minor 和未知字段都必须 fail closed。

#### Scenario: Consumer 未支持新 minor

- **Given** version 1.1 增加可选 latency breakdown
- **And** Consumer 只声明支持 version 1.0
- **When** Consumer 收到 version 1.1
- **Then** 必须拒绝该结果
- **And** 不得自动忽略未知 minor version 或未知字段

#### Scenario: Consumer 明确升级支持新 minor

- **Given** version 1.1 增加可选 latency breakdown
- **And** Consumer 明确声明支持 version 1.0 和 1.1
- **When** Consumer 收到合法 version 1.1 结果
- **Then** Consumer 可以按 version 1.1 Schema 接受该结果

#### Scenario: 修改 anomaly score 数值范围

- **Given** version 1 定义 score 范围为 `[0, 1]`
- **When** Producer 希望改成任意未归一化数值
- **Then** 必须提升 major version

### Requirement: 结果身份必须区分相同重放、内容冲突和同一质检下的多结果

对于相同 `result_id`，JSON 规范化后语义字段相同的重复结果可以视为安全重放；语义字段不同的结果必须视为冲突，不得静默覆盖。相同 `inspection_id` 下不同 `result_id` 表示多份独立视觉结果，不得仅因属于同一质检而判定冲突。

#### Scenario: 完全相同的 recorded result 被重复发送

- **Given** Consumer 已见过相同 `result_id` 和结果内容
- **When** 再次收到相同结果
- **Then** 可以将其识别为重复重放
- **And** 不得制造新的业务事实

#### Scenario: 相同 result identity 出现不同 score

- **Given** Consumer 已见过某 `result_id` 的结果
- **When** 再次收到相同 `result_id` 但不同 `anomaly_score` 的结果
- **Then** 必须标记为 Contract conflict
- **And** 不得静默用新结果覆盖旧结果

#### Scenario: 同一 inspection 产生多份结果

- **Given** 两份结果具有相同 `inspection_id`
- **And** 两份结果具有不同 `result_id`
- **When** Consumer 校验它们的身份关系
- **Then** 不得仅因 `inspection_id` 相同而标记为 Contract conflict
- **And** 哪份结果成为业务权威结果必须由后续业务领域规则决定

### Requirement: 模型 Score 仅在明确版本语义内解释

Consumer 不得假设不同模型版本的 `anomaly_score` 已校准为可直接比较的业务置信度。

#### Scenario: 比较两个模型版本

- **Given** 两个结果来自不同模型版本
- **When** 业务逻辑需要比较风险
- **Then** 不得仅按 score 大小认定某版本更严重
- **And** 必须使用明确的校准或业务策略，该策略不属于本 Change
