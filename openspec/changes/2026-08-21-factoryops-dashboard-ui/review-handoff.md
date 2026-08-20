# Review Handoff

- Change：`2026-08-21-factoryops-dashboard-ui`
- 分支：`codex/factoryops-dashboard-ui`
- worktree：`.worktrees/factoryops-dashboard-ui`
- stacked base：`a2a2f1ac`
- 状态：`review-handoff-ready`
- 入口：`frontend/dashboard.html`；本地运行 `python -m http.server 4173` 后打开 `http://127.0.0.1:4173/dashboard.html`。
- 独立审查：0 Critical / 0 Important；已验证只读、XSS escaping、文件加载错误保留当前视图、移动侧栏折叠。
- 已知 Minor：Snapshot 只做浅层结构校验，未知状态只显示通用 class；后续可增强，不影响当前展示。
