# Verification

状态：`applying`。

## TDD 与局部证据

- 初始 RED：模块缺失，测试 collection fail；首轮 GREEN 又实际暴露 Run counters 从未维护及 Execution Contract 不接受 `RSK-*` decision ID。
- 取舍：以锁定的 Task/Execution 集合作为 readiness 真值，在终态校准 Run counters；Risk 用 evidence ref 绑定，`decision_id` 保持 null，不伪造 `DEC-*`。
- 局部真实 MySQL：completion 单测 `6 passed in 19.85s`。
- 相关 Approval/resume/worker completion 联合：`43 passed in 80.90s`。
- 覆盖成功、相同重放、并发 identical、未完成 Task、双聚合中点失败回滚、transition identity split。

## 全量验证

- Agent：`252 passed in 552.06s`。
- Contract：`154 passed in 2.29s`。
- Java `mvn verify -q`：退出码 0；XML `21 reports / 85 tests / 0 failures / 0 errors / 0 skipped`。
- Ruff check/format、`git diff --check` 通过；`git status --short -- dataset` 无输出。

## 独立首审修复

首审为 0 Critical / 4 Important：业务副作用早于 readiness、Task/Execution 归属与 history 不完整、Run 早期 history 未验证、10 秒 admission 小于 30 秒业务 timeout。新增 RED 覆盖后修复为：

- resume transaction 的 pre-business hook 在 Java 调用前锁定/验证 Coordinator、Task、completion Execution 和 Run 全历史；实际 completion 事务再次验证。
- Task/Execution 强制同 task/run/role，并验证 Task/Execution current Contract 与 revision 0→current history。
- Run 强制验证 revision 0→current 完整合法 chain 与 tail/current。
- admission 改为 35 秒；10.5 秒慢赢家并发回归要求 `APPLIED + DUPLICATE_IDENTICAL`。
- 修复后 completion + resume 局部为 `21 passed in 62.01s`。
