# Verification

状态：`review-handoff-ready`。

- stacked base：`d5dba59c52a0121f1df7f227c6817683fecab89d`
- Risk Contract 局部：10 passed。
- 全 Contract：135 passed。
- Ruff check/format、JSON Schema：通过。
- Agent Service 全量：Docker Desktop 在本轮不可用，未能完成真实 MySQL/Testcontainers 验证；Contract-only tests 通过。
- Java `mvn verify -q`：Docker Desktop 在本轮不可用，9 个既有 Testcontainers integration tests 启动失败；非本 Change 代码失败。
- `dataset/`：未修改。

首审发现 2 个 Important：v1.1 canonical/relation 默认版本缺失，以及 schema subject 字段互斥不足；另修复 source 参数混用校验和 Fusion key 错误文案。修复后局部 10 passed、全 Contract 135 passed，等待复审。

限制证据：Docker named pipe `//./pipe/dockerDesktopLinuxEngine` 不存在，导致 Agent Service 的 Testcontainers 用例无法启动，Java 也有 9 个既有 Docker integration tests 启动失败；不得将其记为通过。

覆盖 v1.0 Recommendation 兼容、v1.1 Fusion subject、Fusion provenance mismatch、跨 subject binding、decision key 派生、canonical relation 和既有 gate 负向规则。
