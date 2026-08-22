# FactoryOps 多批次检测队列设计

本设计的规范性来源是 `openspec/changes/2026-08-22-scan-factoryops-batch-queue/`。

系统把用户明确选择的 `factoryops` 根目录视为批次入口，把每个直接子目录视为独立批次。浏览器冻结每个批次的图片清单并提交给本地服务；服务端持久化队列、顺序派发独立 Run，并用确定性路由器将结果分为质检通过、待复检、待审批或失败。任一批次等待人工、失败或取消时，其他批次继续运行。

质检通过只表示 `QA_ACCEPTED`，不直接将 Java 业务 Batch 迁移为 `RELEASED`。需要 `HOLD_BATCH`、`STOP_LINE` 等高风险动作的批次仅生成待审批事实；审批操作、权限校验和 Java Business API 副作用由后续独立 Change 实现。

本地目录队列继续明确标记为 HTTP 触发，不伪造 Kafka。Kafka 保持 Business World 与 Agent World 的可靠事件边界，不承担 Agent 自由聊天或前端进度动画。
