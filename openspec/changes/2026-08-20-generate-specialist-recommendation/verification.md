# Verification

状态：`review-handoff-ready`；Owner Review/Learning 延后。

- stacked base：`ccf2bd748b26e92af870e57075b68381c068638d`
- TDD RED 1：测试收集因 `factoryops_agent_service.specialist_generation` 不存在而失败。
- TDD RED 2：generation command/service 尚不存在，测试收集失败。
- generation 最终局部真实 MySQL/纯 provider：11 passed in 33.49s（独立复审实跑）。
- Worker start/completion/retry + Recommendation 最终相关真实 MySQL：29 passed in 123.91s（独立复审实跑）；本会话合并执行 40 passed in 166.08s。
- Agent Service 最终全量：193 passed in 652.53s。
- Contract 全量：135 passed in 2.65s。
- Java `mvn verify -q`：退出码 0；20 reports、65 tests、0 failures/errors/skipped。
- 本 Change 修改文件 Ruff check/format、`git diff --check`：通过。全 Agent 目录 Ruff 仍有 22 个既有 import-order baseline finding，本 Change 未批量改写无关文件。
- `git status --short -- dataset`：无输出。

覆盖 recorded provider 隔离/缺配置、确定性 identity、RUNNING 与 terminal replay 不调用 provider、provider provenance/evidence/artifact 越界、provider timeout、非法 draft、barrier 强制的真实并发 identical、context mismatch，以及 provider 调用期间 parent 收口、snapshot/provenance 漂移后的 persistence fencing。

独立审查首轮发现 5 个 Important：未授权 evidence/artifact 与 provider identity、replay identity 不完整、snapshot TOCTOU、raw reader 绕过 Contract、并发测试未强制竞争；`856ab0f` 修复。复审再发现 provenance TOCTOU 与 terminal replay 2 个 Important；`b160acc` 修复。最终复审结论：0 Critical、0 Important。

为复用完整 lifecycle reader，本 Change补齐 Worker Start/Retry/Completion 已有 reason code 对应的非空 message；未改变状态机或事务边界。剩余范围限制：真实模型 adapter 与可信 Tool/Artifact 产物授权仍由后续独立 Change 实现；当前 recorded provider 不允许输出 artifact refs。
