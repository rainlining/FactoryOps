# Verification

- retry 真实 MySQL：`7 passed in 24.07s`；覆盖原子 attempt replacement、顺序/并发 identical/conflicting、跨 Task request 竞争、ownership/安全码/预算拒绝、注入回滚和 retry 后 Completion。
- Start/Completion 相关局部：`14 passed`；migration/lifecycle/retry 组合：`45 passed`。
- Contract：`99 passed in 0.79s`。
- Agent Service 最终全量：`143 passed in 265.26s`。
- Java `backend/business-service mvn verify -q`：exit 0；20 份 XML，`65 tests, 0 failures/errors/skipped`；既有负向 Kafka 日志符合预期。
- Ruff check/format：通过，58 files formatted。
- `git diff --check` 通过，Change diff 与 `dataset/` 无交集。

初次 Agent 全量为 `5 failed, 137 passed`，五项失败均为 migration 数量/末版本仍期待 8/008；更新为 9/009 后受影响组合 `45 passed`。独立 diff 审查发现 Important：既有 Completion 把 Task revision 硬编码为 `1→2`，使 retry attempt 2 无法完成；已改为锁定 snapshot 的 `n→n+1` 并由端到端测试证明 attempt 2 完成后 Task 为 SUCCEEDED revision 3。
