# Verification：2026-08-15-start-agent-run-from-inbox

## 当前状态

- `change_status`: `applying`
- `technical_verification`: `pending`
- `learning_gate`: `pending`

## 基线

2026-08-15 创建 worktree 后执行 `python -m pytest -q`：30 个非 Docker 测试通过；Docker Desktop 未运行导致 Testcontainers 相关 3 failed、18 errors。此时尚无 Change 文件修改，因此记录为环境基线限制。实现前必须启动 Docker 并重新取得完整绿色基线。

## 范围检查

- [x] 未启动 Coordinator、LLM 或 Run `RUNNING` 迁移。
- [x] 未增加 Inbox 状态、Lease 或 migration。
- [x] 未修改 `dataset/`。
- [x] `git diff --check` 通过。

## 实施中的验证证据

2026-08-15，在 Docker Desktop 未运行的环境中：

- `python -m ruff check src tests`：通过。
- `python -m ruff format --check src tests`：28 files already formatted。
- 非 Docker 局部集合：51 passed。
- `test_inbox_mysql.py` 与 `test_kafka_mysql_e2e.py` 已完成测试代码，但尚未取得真实容器运行证据。

不得将上述局部结果解释为 `technically-verified`。启动 Docker 后必须重新执行完整 Agent Service、Contract、Java 与 diff 验证。
