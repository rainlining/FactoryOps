# 设计：批次作战室

## 1. 产品目标

用户导入一个任意数量图片的批次后，应能持续回答四个问题：系统正在做什么、处理到哪里、各 Agent 如何形成结论、最终应采取什么批次动作。

## 2. 页面信息架构

工作流页按业务阅读顺序排列：

1. **批次状态栏**：批次名称、产品总数、总进度、当前阶段、已耗时、最近活动时间、取消入口。
2. **Agent 协作拓扑**：`图片队列 → Vision → Quality/Production/SLA → Coordinator → Risk → 审批/执行`。
3. **批次审查结论**：合格/异常数量、主要异常、影响范围、Coordinator 建议、Risk 结论、审批要求。
4. **产品证据明细**：按需展开逐张 Vision 和专家依据。
5. **事件与技术详情**：Run/Task/Execution ID、revision、Trace；Kafka provenance 只在真实存在时显示。
6. **历史运行**：查看保存的批次结论、协作事件和证据，不再次调用模型。

现有固定 `demoSnapshot` 不得继续冒充当前上传批次；它只能出现在标注为“录制示例”的独立区域或服务不可用的明确 fallback 中。

## 3. 真实进度模型

后端为每次 Run 保存有序 `progress_events`：

```json
{
  "sequence": 12,
  "occurred_at": "2026-08-22T10:00:00Z",
  "stage": "VISION",
  "agent_role": "vision",
  "status": "RUNNING",
  "completed_units": 6,
  "total_units": 10,
  "product_ref": "part-006.png",
  "summary": "正在检查第 6 个产品"
}
```

阶段为 `INGEST`、`VISION`、`SPECIALISTS`、`COORDINATOR`、`RISK`、`APPROVAL`、`COMPLETED`。状态为 `PENDING`、`RUNNING`、`SUCCEEDED`、`FAILED`、`RETRYING`、`CANCELLED`。

百分比必须由已完成的真实工作单元计算，不按定时器模拟。`sequence` 对同一 Run 严格递增；前端忽略重复或倒序事件。超过配置的静默阈值没有新事件时显示“长时间无进展”，但不得自行判定失败。

首版本地服务使用 `GET /api/runs/{run_id}/events?after=<sequence>` 短轮询，避免引入新基础设施；接口只返回已持久化事件。未来可无损替换为 SSE。

## 4. 批次分析语义

逐张 Vision 与 Specialist 结果属于证据。只有所有可用产品证据完成或被明确标记失败后，Coordinator 才生成唯一批次 Fusion；Risk 只审查该批次 Fusion。最终页面不把单产品 Coordinator/Risk 文本当作批次结论。

部分产品失败时，批次结论必须包含成功数、失败数和证据完整性，禁止静默忽略失败产品。取消后不生成成功结论；已完成事件和证据仍可审计。

## 5. Agent 协作拓扑

每个节点展示状态、开始/结束时间、耗时、输入摘要和输出摘要。边表示结构化 Contract 或持久化事实的传递，不表示自然语言聊天。三个 Specialist 可以并行；只有满足 readiness 后 Coordinator 节点才进入 RUNNING；Risk 必须等待批次 Fusion。

前端动画仅用于表现已经收到的状态迁移，不提前播放未来阶段。失败节点显示错误分类和重试次数；重试不得清除先前尝试的 Trace。

## 6. Kafka 展示边界

Kafka 的职责是连接 Java Business World 与 Python Agent World，承载可靠的质量事件入口，并提供 topic、partition、offset 和 redelivery provenance。Agent 内部协作继续使用版本化 Contract 和持久化 Task/Execution，不用 Kafka 聊天。

若当前 Run 来自真实 Kafka Inbox，技术详情显示 topic、partition、offset、event_id 和消费结果；若演示运行由 HTTP 直接启动，显示“本次本地运行未经过 Kafka”。禁止生成假的 offset 或 topic 动画。

## 7. 持久化与回放

SQLite 本地演示库保存 Run payload、批次结论、产品证据和 `progress_events`。历史查看只读取保存内容。显式“重新运行”创建新 Run，并保留 `derived_from_run_id`；不得改写原 Run。

## 8. 失败路径

- Agent API 失败：记录 FAILED 事件、角色、产品和可读原因，允许安全重试。
- 轮询失败：页面保留最后状态并显示连接中断，不把 Run 改为失败。
- 浏览器取消：请求取消与服务端 Run 取消状态必须分开表达；无法确认服务端取消时显示“取消请求已发送”。
- 历史数据缺字段：降级展示可用信息，并标注旧版记录。
- Kafka provenance 缺失：显示未经过/不可用，不猜测。

## 9. 测试策略

- 进度事件序列、阶段迁移和百分比计算单元测试。
- SQLite Run、事件、证据与历史回放集成测试。
- 真实 HTTP 测试覆盖运行、轮询、取消、失败、重试和只读历史。
- 浏览器测试验证协作节点状态、批次结论优先级、旧快照隔离和回放零模型调用。
- 回归运行 Java、Agent Service、Contract、Ruff、Node syntax、Python compile、diff check，并确认 `dataset/` 未修改。

## 10. 取舍

采用持久化事件加短轮询，优先保证真实、可恢复和易验证；不采用定时动画假进度。首版不把完整 Kafka 链路强行接入本地模型演示，因为这会扩大业务运行时范围；页面诚实显示当前 Run 的 transport mode。
