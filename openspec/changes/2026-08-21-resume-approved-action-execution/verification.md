# Verification

状态：`technically-verified`，等待独立审查。

## TDD 与局部验证

- 初始 RED：缺少 saga/HTTP adapter；新增 Run fence 回归进一步证明旧编排在 Java 外调期间可被并发 cancel 抢占，导致已执行动作无法恢复 Run。
- GREEN：`python -m pytest -q services/agent-service/tests/test_approved_action_resume_mysql.py services/agent-service/tests/test_approved_action_http_client.py` 为 `16 passed in 27.80s`。
- 真实 MySQL 覆盖 applied、terminal/business/transition replay、receipt mismatch、HTTP failure 后保持 WAITING、Java 成功后 Agent failure 的恢复、并发 identical 单 transition，以及外调期间并发 cancel 被 Run row fence 阻塞。
- 本地真实 HTTP server 覆盖 path/header/空 body、409、malformed JSON、timeout 与安全 timeout 范围。

## 全量验证

- Agent：`237 passed in 524.94s`。
- Contract：`154 passed in 2.40s`。
- Java `mvn verify -q`：退出码 0；XML `21 reports / 85 tests / 0 failures / 0 errors / 0 skipped`。
- 本 Change Python 文件 Ruff check/format 通过。
- `git diff --check` 通过；`git status --short -- dataset` 无输出。

## 限制

本 Change 只恢复 Run 到 RUNNING；Coordinator Execution/Run success 收口、REJECTED/EXPIRED 策略和 UI 属于后续 Change。Agent 事务在 Java HTTP 调用期间持有单个 Run row lock，生产 timeout 强制 `(0,30]` 秒；吞吐取舍用于防止 cancel/suspend 与已批准业务动作 TOCTOU。
