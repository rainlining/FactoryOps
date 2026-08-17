# 技术验证

- 最新 Dispatch stacked base：`af23d07fa94355508378f3561fc505f08f18285c`；吸收 merge：`e8f47ebef8e25ea46e5f090ae165d4fc4bca2252`。
- Lease/dispatch 真实 MySQL：`6 passed in 12.44s`。覆盖 claim/renew/release、未过期竞争、过期接管、陈旧 owner release/renew fencing 和非法 renew TTL。
- Agent Service 全量：`122 passed in 199.02s`。
- Contract：`99 passed in 1.41s`。
- Java `mvn verify -q`：exit code 0；20 份 XML，`65 tests, 0 failures, 0 errors, 0 skipped`。
- Ruff check：通过；format check：`54 files already formatted`。
- `git diff --check` 通过；相对 `af23d07` 仅 claim OpenSpec、migration 006、lease Service 和相关测试，无 `dataset/`。

初始独立审查发现 1 Important：数据库 expiry 时区解释不稳定；已修复为按 UTC 恢复。Stacked 恢复审查再发现 renew 未统一校验 TTL、陈旧 token failure exercise 缺少自动化证据；已补范围校验和真实 MySQL fencing 测试。复审无 Critical/Important。

限制：lease 只提供短期 ownership，不推进 Task、不创建 Execution、不含 Worker heartbeat/background cleanup；过期行在下一 claim 原位接管。

技术状态为 `review-handoff-ready`。这是 Deep Change，Owner 修改、陈旧 token 故障实验与 Learning Gate 尚未完成。
