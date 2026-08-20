# Verification

状态：`technically-verified`，等待独立子 Agent 审查。

- stacked base：`ccf2bd748b26e92af870e57075b68381c068638d`
- TDD RED 1：测试收集因 `factoryops_agent_service.specialist_generation` 不存在而失败。
- TDD RED 2：generation command/service 尚不存在，测试收集失败。
- generation 局部真实 MySQL/纯 provider：8 passed in 18.30s。
- Recommendation/Worker 相关真实 MySQL：29 passed in 100.68s。
- Agent Service 全量：190 passed in 436.11s。
- Contract 全量：135 passed in 2.65s。
- Java `mvn verify -q`：退出码 0；20 reports、65 tests、0 failures/errors/skipped。
- Ruff check/format、`git diff --check`：通过。
- `git status --short -- dataset`：无输出。

覆盖 recorded provider 隔离/缺配置、确定性 identity、首次保存、replay 不调用 provider、provider timeout、非法 draft、真实并发 identical、context mismatch、provider 调用期间 parent 完成后的 persistence fencing。

已知上游事项：Worker start 产生的 Execution 行带 status reason code 且 message 为空，通用 `AgentExecutionLifecycleService.get_execution` 会因 Contract message 非空约束拒绝该行。本 Change 不扩展范围修复生命周期；generation preflight 只读取并验证所需 ownership/context typed fields，最终 persistence 仍在事务中锁定 Task/Execution。该解码一致性应作为独立 follow-up。
