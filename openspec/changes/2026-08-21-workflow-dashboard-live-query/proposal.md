# Change 提案：Dashboard Snapshot API 接入

- `change_id`: `2026-08-21-workflow-dashboard-live-query`
- `status`: `review-handoff-ready`
- `learning_level`: `delegated`
- `depends_on`: `2026-08-21-factoryops-dashboard-ui`

将 Dashboard 的数据来源从内置 JavaScript 对象切换为只读 `/api/snapshot`，并提供本地 demo server 与录制 Snapshot。页面仍支持用户加载 JSON 文件，API 不包含任何写入或业务动作。

非目标：不连接生产数据库、不新增认证、不改变 Agent Query Service、不执行审批或业务动作、不读取 `dataset/`。
