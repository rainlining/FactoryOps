# Review Handoff

- Change：`2026-08-21-workflow-dashboard-live-query`
- 分支：`codex/workflow-dashboard-live-query`
- worktree：`.worktrees/workflow-dashboard-live-query`
- stacked base：`006c869d`
- 状态：`review-handoff-ready`
- 入口：`frontend/demo_server.py`；运行 `python frontend/demo_server.py` 后打开 `http://127.0.0.1:4173/dashboard.html`。
- API：`GET /api/snapshot`；前端 API 失败时保留 demo fallback，文件加载仍可替换 Snapshot。
- 独立审查：0 Critical / 0 Important。
