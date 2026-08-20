# Change 提案：Executive Demo Packaging

- `change_id`: `2026-08-21-executive-demo-packaging`
- `status`: `review-handoff-ready`
- `learning_level`: `delegated`
- `depends_on`: `2026-08-21-recorded-demo-scenario`

将 FactoryOps 的前端、只读 API 和录制检测场景整理成老板可直接查看的演示包：一条 PowerShell 命令启动本地 server，页面默认显示检测图、业务摘要和完整决策链，并在页面显式标识 recorded demo/local read-only。

非目标：不部署生产环境、不新增认证、不连接生产数据库、不修改 dataset、不提供业务操作按钮。
