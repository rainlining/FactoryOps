# Proposal：扫描 FactoryOps 批次队列

- `change_id`: `2026-08-22-scan-factoryops-batch-queue`
- `status`: `proposed`
- `learning_level`: `delegated`
- `depends_on`: `2026-08-22-visualize-batch-agent-collaboration`

## 动机

当前工作台一次只能手动导入一个批次文件夹。`dataset/factoryops/` 已包含多个独立批次，但系统不能把它们识别为待检队列、连续执行或汇总展示。操作者因此必须反复选目录，也无法在一个批次等待人工处理时继续检查后续批次。

## 范围

- 把用户明确选择的根目录视为“批次入口”，其直接子目录各自代表一个独立批次。
- 扫描批次及图片，显示待处理、检测中、质检通过、待复检、待审批、失败和已取消状态。
- 以有限并发连续处理队列；每个批次拥有独立 Run、进度、Agent 输出、结论、Trace 和历史记录。
- 通过文件相对路径、大小和内容摘要形成稳定输入身份，避免同一次扫描或重复扫描静默重复检测。
- 根据结构化批次结论和确定性策略，将正常批次标记为“质检通过”，将风险动作路由到待复检或待审批区。
- 一个批次失败、取消或等待审批不得阻塞其他批次。
- 支持暂停继续派发、取消尚未开始的批次，以及重试失败批次。

## 非目标

- 不把整个根目录合并成一个超级批次。
- 不将“质检通过”直接等同于业务 Batch 的 `RELEASED` 状态。
- 不在本 Change 实现批准、驳回、要求复检的操作，也不执行 `HOLD_BATCH` 或 `STOP_LINE`。
- 不把当前本地上传链路伪装为 Kafka；本 Change 不修改 Kafka Producer、Consumer 或 Outbox。
- 不修改 `dataset/`，也不自动监视任意磁盘目录。
- 不引入账号、角色权限或生产部署能力。

## 依赖关系

本 Change 复用上一 Change 的异步 Run、持久化进度事件、批次级结论、Agent 协作拓扑和只读历史回放。后续 `operate-batch-approval-from-workbench` 将消费本 Change 产生的待审批事项，并连接既有审批 Contract 与 Java Business API。

## 学习等级

`delegated`。本 Change 复用已经实现并审查过的 Run、进度和失败恢复模式，新增的是入口目录的队列编排与确定性路由，没有改变 Java 业务表所有权、Kafka offset 或审批事务语义。
