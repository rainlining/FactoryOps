# Inspection Result Intake 规格

## 新增需求

### Requirement: Java API 接收 Contract 1.0

系统必须通过 `POST /api/v1/inspection-results` 接收 Vision Inspection Contract 1.0。首次创建返回 201、`replayed=false` 和 `disposition=CREATED`；完全相同重放返回 200、`replayed=true` 和 `disposition=REPLAYED`。

#### Scenario: 首次创建
- **Given** 合法且尚不存在的 `result_id`
- **When** 提交结果
- **Then** 返回 201
- **And** MySQL 只新增一行不可变结果

#### Scenario: 相同重放
- **Given** 已存在相同 `result_id` 和规范化内容
- **When** 再次提交
- **Then** 返回 200 且 `replayed=true`
- **And** 不新增或覆盖记录

### Requirement: Contract 失败具有稳定状态和路径

无法解析 JSON 返回 400；可解析但违反 Contract 返回 422；单份合法但与已有不可变身份冲突返回 409。422 只返回固定优先级的第一个 issue。

#### Scenario: Score 越界
- **Given** `anomaly_score=1.01`
- **When** 提交
- **Then** 返回 422
- **And** issue path 为 `$.observation.anomaly_score`

#### Scenario: 判断矛盾
- **Given** score 高于 threshold 但 `is_anomaly=false`
- **When** 提交
- **Then** 返回 422
- **And** code 为 `inconsistent_anomaly_decision`

### Requirement: 相同结果身份不得表达不同内容

相同 `result_id`、不同规范化内容必须返回 409，且不得覆盖首次成功内容。

#### Scenario: 冲突重放
- **Given** 已保存 `result-1001`
- **When** 提交相同 ID 但不同 score
- **Then** 返回 409 `result_identity_conflict`
- **And** 数据库仍保存原内容

### Requirement: 同一质检允许多份结果

相同 `inspection_id`、不同 `result_id` 必须分别保存；当前能力不得选择权威结果。

### Requirement: JSON 内容规范化后比较

Object key 必须排序；array 顺序保持；number 使用 BigDecimal 去除无意义尾零并输出普通十进制，负零归一为零；结果以 UTF-8 最小 JSON 计算 SHA-256。

#### Scenario: 表达不同但语义相同
- **Given** 两份结果只存在 key 顺序、`0.60/0.6` 或指数/普通十进制差异
- **When** 比较相同 `result_id`
- **Then** 必须视为相同重放

### Requirement: MySQL 是并发最终防线

应用预查询不得替代数据库唯一约束。并发唯一键失败必须回滚当前事务，并在新 READ COMMITTED 事务中读取赢家，再判断 replay 或 conflict。

#### Scenario: 相同并发请求
- **Given** 两个线程并发提交相同结果
- **When** 两者都经过不存在预查询
- **Then** 数据库只保存一行
- **And** 一个结果为 created，另一个为 replayed

#### Scenario: 冲突并发请求
- **Given** 两个线程并发提交相同 `result_id`、不同内容
- **When** 竞争写入
- **Then** 只保存一个不可变赢家
- **And** 另一请求返回 409

### Requirement: 不收紧已有 Contract 精度和长度

分数/阈值必须以规范化十进制文本精确保留；未限制长度的 ID 必须保存原文，并使用 SHA-256 二进制派生键建立唯一/查询索引，hash 命中后必须比较原文防御碰撞。
