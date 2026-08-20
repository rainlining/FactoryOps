# Change 提案：Workflow Dashboard 演示页

- `change_id`: `2026-08-21-demo-dashboard`
- `status`: `review-handoff-ready`
- `learning_level`: `delegated`
- `depends_on`: `2026-08-21-demo-query-api`

本 Change 将已脱敏的 Workflow Snapshot 渲染为无需后端写入的静态 HTML，方便个人展示 Run 进度、Agent Tasks、Coordinator、Fusion、Risk 和 Approval 状态。页面只接受已查询的 snapshot，不自行访问数据库，也不执行任何动作。

非目标：不新增 HTTP 服务、认证、审批按钮、业务动作、实时刷新、dataset 处理或跨数据库 Business Receipt 聚合。
