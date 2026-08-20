# Review Handoff

- Change：`2026-08-21-executive-demo-packaging`
- 分支：`codex/executive-demo-packaging`
- worktree：`.worktrees/executive-demo-packaging`
- stacked base：`d3942154`
- 状态：`review-handoff-ready`
- base commit：`d3942154`
- 最终 HEAD：`b469b11`
- 入口：`scripts/start_factoryops_demo.ps1`
- 演示 URL：`http://127.0.0.1:4173/dashboard.html`
- 调用链：PowerShell 启动脚本 → `frontend/demo_server.py` → 静态 `dashboard.html` 与只读 `/api/snapshot`；图片通过固定 recorded endpoint 提供。
- 成功路径：启动后页面与 snapshot 均返回 200，页面展示检测图、批次、建议和决策链。
- 失败路径：对 snapshot 发 POST 返回 405；缺失 server 文件时脚本立即报错。
- 验证：见 `verification.md`，包含真实 HTTP、diff check 与 dataset 状态检查。
- 已知限制：本地 recorded demo，不接生产数据库、不提供审批/业务动作、不替代真实 Vision Service。
- Review 恢复：在本 worktree 阅读 proposal → design → script → `frontend/demo_server.py` → docs → verification；不得与其他会话并行修改本 Change。
