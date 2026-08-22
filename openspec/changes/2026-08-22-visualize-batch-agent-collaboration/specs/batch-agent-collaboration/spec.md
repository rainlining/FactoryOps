# 批次 Agent 协作可视化规格

## Requirement: 进度必须来自真实工作事实

系统必须展示当前阶段、完成单元、总单元、百分比、已耗时和最近活动时间。百分比不得由纯前端定时器模拟。

### Scenario: 批次逐张检测

- **WHEN** 10 张图片中的第 6 张 Vision 检测已开始
- **THEN** 页面显示 Vision 阶段、`6/10` 或对应真实完成量，并标识当前产品

### Scenario: 长时间没有新进展

- **WHEN** 超过静默阈值未收到新事件
- **THEN** 页面显示“长时间无进展”且保留最后事实，不自行宣布失败

## Requirement: 最终结果必须以批次为单位

系统必须把产品诊断作为证据，并由 Coordinator 和 Risk 对整个批次生成唯一结论。

### Scenario: 批次完成

- **WHEN** 批次所有产品均得到成功或明确失败结果
- **THEN** 页面优先显示产品总数、成功/失败数、主要异常、批次建议、风险和审批要求

## Requirement: Agent 协作必须可观察

页面必须展示 Vision、Quality、Production、SLA、Coordinator、Risk 和 Approval 的真实状态、耗时及输入输出摘要。

### Scenario: Specialist 并行完成

- **WHEN** 三个 Specialist 状态陆续完成
- **THEN** 对应节点独立更新，Coordinator 仅在 readiness 满足后进入运行状态

## Requirement: Kafka provenance 不得伪造

页面只在 Run 具有真实 Kafka provenance 时显示 topic、partition、offset 和 event_id。

### Scenario: HTTP 本地运行

- **WHEN** Run 由本地 HTTP 入口直接创建
- **THEN** 页面明确显示“本次本地运行未经过 Kafka”

## Requirement: 历史查看必须零模型调用

历史记录必须保存批次结论、产品证据和进度事件，并能重建协作过程。

### Scenario: 查看历史 Run

- **WHEN** 用户点击“查看记录”
- **THEN** 系统只读取保存数据，不调用任何 Agent Provider，也不创建新 Run
