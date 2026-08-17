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

## Review/Learning 验证

- Owner 边界测试：`test_lease_ttl_upper_boundary_is_inclusive`，真实 MySQL；TTL=3600 成功，TTL=3601 被拒绝。
- Failure/Debug Exercise：`test_expired_lease_takeover_fences_stale_owner`，真实 MySQL；worker-2 在过期后接管，worker-1 旧 token 的 release/renew 均被拒绝，worker-2 lease 未被删除或覆盖。
- Claim/Dispatch 局部复验：`7 passed in 11.75s`。
- 最终 diff review：仅当前 Change 的 lease 测试和工件发生变化；`dataset/` 未修改，`git diff --check` 通过，无未处理 Critical/Important。
- 项目所有者已在其他地方完成 Learning Gate，本 Change 可进入归档准备。
