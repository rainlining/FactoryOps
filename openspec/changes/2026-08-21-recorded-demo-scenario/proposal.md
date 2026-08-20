# Change 提案：Recorded Demo Scenario

- `change_id`: `2026-08-21-recorded-demo-scenario`
- `status`: `review-handoff-ready`
- `learning_level`: `standard`
- `depends_on`: `2026-08-21-workflow-dashboard-live-query`

为老板演示准备一条可重复的产品检测场景：选定 sheet-metal 检测图，提供脱敏的缺陷摘要、批次影响和对应 Workflow Snapshot。原始图片保留在 `dataset/`，不修改、不复制；本地 demo server 通过固定白名单路径只读提供它。

非目标：不修改 dataset、不声称图片由真实模型推理、不改变 Risk/Approval/Business Action 状态、不引入上传功能或任意文件读取。
