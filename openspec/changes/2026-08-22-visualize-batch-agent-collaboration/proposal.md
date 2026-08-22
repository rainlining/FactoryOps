# Proposal：可视化批次 Agent 协作

- `change_id`: `2026-08-22-visualize-batch-agent-collaboration`
- `status`: `review-handoff-ready`
- `learning_level`: `delegated`
- `depends_on`: `2026-08-21-executive-demo-packaging`

## 动机

现有工作台在一次同步请求结束前只显示“处理中”，无法区分正常执行与卡死；首屏展示固定录制快照和内部生命周期字段，不能代表用户刚导入的批次；各 Agent 输出彼此割裂，也没有体现 Kafka 在真实系统中的可靠事件边界。

## 范围

- 为批次运行提供真实、单调递增的阶段进度和最近活动时间。
- 以批次为最终审查单位，产品级诊断只作为证据明细。
- 用协作拓扑展示 Vision、三个 Specialist、Coordinator、Risk 与审批的真实状态、输入摘要、输出摘要和耗时。
- 保存进度事件和 Agent 输出，使历史查看不调用模型即可重建协作过程。
- 将固定录制快照与工程字段移入明确标注的技术详情区。
- 仅在运行真实经过 Kafka 时展示 Kafka topic/partition/offset；本地同步模式明确标注“未经过 Kafka”。

## 非目标

- 不伪造进度百分比、Kafka 消息或 Agent 输出。
- 不把 Kafka 用作 Agent 自由聊天层。
- 不在本 Change 重写 Java 业务状态机、Kafka Producer/Consumer 或既有 Agent Contract。
- 不修改 `dataset/`。
- 不实现生产环境认证、横向扩缩容或远程部署。

## 学习等级

`delegated`。本 Change 组合既有 Run、Task、Recommendation、Fusion、Risk、Approval 与 Kafka provenance，并主要改善查询、流式可观测性和前端表达，不引入新的业务所有权或事务语义。
