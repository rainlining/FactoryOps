# Change 提案：FactoryOps 正式 Dashboard 前端

- `change_id`: `2026-08-21-factoryops-dashboard-ui`
- `status`: `review-handoff-ready`
- `learning_level`: `delegated`
- `depends_on`: `2026-08-21-demo-dashboard`

当前项目已有 Snapshot 查询和静态 HTML renderer，但缺少一个可以直接向个人展示的正式前端。这个 Change 建立一个无构建依赖的 FactoryOps Dashboard，加载 Snapshot JSON 后展示 Run、Task、Coordinator、Fusion、Risk、Approval 和业务动作结果。

非目标：不新增后端 API、数据库写入、审批按钮、业务动作、认证、实时推送或 dataset 读取。
