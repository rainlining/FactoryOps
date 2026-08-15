# Verification：2026-08-15-start-agent-run-from-inbox

## 当前状态

- `change_status`: `review-handoff-ready`
- `technical_verification`: `passed`
- `learning_gate`: `pending`

## 基线

2026-08-15 创建 worktree 后执行 `python -m pytest -q`：30 个非 Docker 测试通过；Docker Desktop 未运行导致 Testcontainers 相关 3 failed、18 errors。此时尚无 Change 文件修改，因此记录为环境基线限制。实现前必须启动 Docker 并重新取得完整绿色基线。

## 范围检查

- [x] 未启动 Coordinator、LLM 或 Run `RUNNING` 迁移。
- [x] 未增加 Inbox 状态、Lease 或 migration。
- [x] 未修改 `dataset/`。
- [x] `git diff --check` 通过。

## 最终验证证据

2026-08-15 启动 Docker Desktop 后，在 commit `f217b7e` 上执行：

- `python -m ruff check src tests`：通过。
- `python -m ruff format --check src tests`：28 files already formatted。
- `python -m pytest -q`：75 passed in 99.98s，包含真实 MySQL 8.4 与 Apache Kafka 4.1.0 Testcontainers。
- `python -m pytest -q tests/test_inbox_mysql.py tests/test_kafka_mysql_e2e.py`：3 passed in 74.80s（修复前目标验证）；修复后的相关 MySQL 测试又随 75 项全量通过。
- 三个 Contract unittest 套件：Agent Run 22、Quality Incident Opened 18、Vision Inspection 17，共 57 passed。
- `mvn verify -q`：exit 0；Surefire/Failsafe XML 汇总 65 tests、0 failures、0 errors、0 skipped，Java 17。
- `git diff --check db7ab6e..f217b7e`：通过。

## 独立审查

首次审查发现两个 Important：版本配置缺少 128 字符上限/确定性创建拒绝会被重试，以及并发测试未强制真实竞态。commit `f217b7e` 增加失败测试和修复后，独立复审结论为 READY：0 Critical、0 Important、0 Minor。

## 剩余限制

- 本 Change 只创建 `PENDING` Run，不负责 Coordinator 启动。
- retryable adapter 失败采用固定 1 秒进程级等待；退避与停机编排不属于本 Change。
- Deep Learning Gate 尚未在独立 Review/Learning 会话完成，因此不得归档或合并 `main`。
