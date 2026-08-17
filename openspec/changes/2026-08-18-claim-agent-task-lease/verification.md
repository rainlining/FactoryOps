# 技术验证

- Migration/Ruff focused：2 passed；Ruff check/format 通过。
- Agent Service 全量（migration 与 lease 实现加入后）：`116 passed in 250.44s`。
- Lease/dispatch 真实 MySQL：首次失败暴露 MySQL naive datetime 与 UTC-aware clock 比较错误；修复后 `5 passed in 25.47s`。
- Contract 与 Java 没有代码变更；沿用紧邻 stacked base 的已执行结果：Contract 99 passed、Java 65 tests/0 failures。当前 Change 额外验证 Python migration 和全量 Agent。
- `git diff --check` 通过，`dataset/` 无修改。

独立审查发现 1 Important：数据库 expiry 时区解释不稳定；已修复为按 UTC 恢复。复审无 Critical/Important。

限制：lease 只提供短期 ownership，不推进 Task、不创建 Execution、不含 Worker heartbeat/background cleanup；过期行在下一 claim 原位接管。

技术状态为 `review-handoff-ready`。这是 Deep Change，Owner 修改、陈旧 token 故障实验与 Learning Gate 尚未完成。
