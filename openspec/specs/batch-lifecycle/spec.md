# Batch Lifecycle 规格增量

## 新增需求

### Requirement: 创建和查询不可变身份的生产 Batch

系统必须通过 `POST /api/v1/batches` 创建 `PRODUCTION + OPEN` Batch，并通过 `GET /api/v1/batches/{batch_id}` 查询完整生命周期快照。身份由 `batch_id`、`product_code`、`production_line` 组成且创建后不可修改；相同身份重放返回 200，不同身份复用 ID 返回 409。

#### Scenario: 并发幂等创建
- **Given** 两个相同身份的请求同时创建不存在的 Batch
- **When** 两者竞争唯一键
- **Then** 数据库只有一行
- **And** 一个结果为 created，另一个为 replayed

### Requirement: Batch ID 和业务代码具有严格格式

Batch ID、Product Code 和 Production Line 必须符合设计中的大写标识符格式；系统不得自动纠正。`SYS-` 为系统保留命名空间，外部创建必须拒绝。

### Requirement: 首次 HOLD 保留不可覆盖的原因和时间

系统必须只允许 `PRODUCTION + OPEN → HELD`，并以条件更新保证并发下只有一个首次命令写入 `held_at`、原因及证据。完全相同命令重放不得覆盖首次事实，不同命令必须冲突。

#### Scenario: 不同 HOLD 命令并发竞争
- **Given** 一个 OPEN Batch 和两个不同原因或证据的合法 HOLD 命令
- **When** 两者并发提交
- **Then** 只有一个命令成为首次赢家
- **And** 另一个返回 `batch_command_conflict`
- **And** 数据库保留赢家的首次时间、原因和证据

### Requirement: QUALITY_ANOMALY HOLD 必须具有精确异常证据

QUALITY_ANOMALY 必须引用 Inspection 和 Result；系统必须验证 Result 存在且异常、属于该 Inspection，并且 Inspection 属于目标 Batch。人工质量冻结与过程异常不要求证据且禁止携带证据字段。

### Requirement: RELEASE 是受保护的内部终态迁移

Domain 和数据库必须支持 `HELD → RELEASED`、相同命令重放和不同命令冲突；`OPEN → RELEASED` 与 `RELEASED → HELD` 必须拒绝。本 Change 不得提供 RELEASE HTTP API。

### Requirement: 历史 Inspection 使用不可操作的系统占位 Batch

V3 必须创建 `SYS-LEGACY-UNASSIGNED`，将历史 Inspection 全部绑定该对象，并使其可查询但不能 HOLD、RELEASE 或接收新 Inspection。迁移不得猜测真实生产归属。

## 修改需求

### Requirement: 创建具有确定输入身份的 Inspection

系统必须通过 `POST /api/v1/inspections` 创建 `PENDING` Inspection。新请求必须包含真实且已存在的 `batch_id`，不可变身份由 `inspection_id`、`batch_id`、`image_uri` 和 `sha256` 组成。缺少 Batch ID 或引用不存在 Batch 返回 422；PRODUCTION + OPEN/HELD 可接收新 Inspection，RELEASED 或系统占位 Batch 返回 409。

#### Scenario: RELEASE 与新建 Inspection 并发
- **Given** 一个 HELD Batch
- **When** 内部 RELEASE 与全新 Inspection 创建并发
- **Then** 两者通过父 Batch 行锁形成明确顺序
- **And** Inspection 先完成则两者成功，RELEASE 先完成则 Inspection 被拒绝

#### Scenario: 已有 Inspection 在 Batch 释放后重放
- **Given** Inspection 已合法创建且 Batch 后来 RELEASED
- **When** 完全相同的创建请求重放
- **Then** 返回 200 replayed
- **And** 不重新应用 Batch 当前接收条件
