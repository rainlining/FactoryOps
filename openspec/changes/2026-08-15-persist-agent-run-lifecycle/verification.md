# Verification：2026-08-15-persist-agent-run-lifecycle

## 当前状态

- `change_status`: `review-handoff-ready`
- `technical_verification`: `passed`
- `learning_gate`: `pending`

## 实际验证

在 2026-08-15 从对应目录执行：

| 范围 | 命令 | 结果 |
| --- | --- | --- |
| Python lint | `python -m ruff check src tests` | 通过 |
| Python format | `python -m ruff format --check src tests` | 通过 |
| Agent Service | `python -m pytest -q` | 48 passed |
| Contract | `python -m unittest discover -s contracts -p "test_*.py" -v` | 57 passed |
| Business Service 回归 | `mvn -q verify` | exit 0；65 tests，0 failure/error/skip |
| Diff whitespace | `git diff --check a5e0da6..HEAD` | 通过 |

Agent Service 测试通过 Docker 启动真实 MySQL 8.4，验证了：

- 空库迁移、从仅有 `001` 的数据库升级、重复运行 migration；
- original/replay 创建、唯一键与外键、Contract 重建；
- snapshot/history 同事务提交与故障回滚；
- transition request 幂等、冲突分类和并发单赢家；
- `PENDING → CANCELLED` 不伪造 `started_at`，`SUSPENDED` 强制 checkpoint。
- replay 同请求不同输入被分类为 conflicting，且 lineage 校验不会遮蔽已有请求分类；
- Clock 回拨造成的非法终态在写事务前被 Contract 校验拒绝，revision/history 不变。

Java 全量回归中的 broker unavailable、missing topic 和连接断开日志来自已有负向测试的主动故障注入；最终 Maven 进程 exit 0。

## 范围检查

- [x] 未连接 Kafka Worker、HTTP、Coordinator 或 Agent Runtime。
- [x] 未修改 `dataset/`。
- [x] `git diff --check` 通过。

## 限制与剩余风险

- 当前只有内部 Application Service，尚无生产入口；后续 Change 才会从 Inbox 驱动 Run 创建。
- MySQL DDL 会隐式提交，migration 的失败恢复依赖版本记录和运维处置；运行时 Run 写事务不受此限制。
- 本 Change 只保存 checkpoint reference，不实现 checkpoint 内容、Resume 或 Replay 执行。

## 独立代码审查

只读审查最初发现两项 Important，均已在 `4cdbc43` 修复并加入真实 MySQL 回归：

1. replay 幂等键的已存在分类提前到 lineage 校验之前；
2. 状态迁移在 SQL 写入前构造候选 snapshot 并执行 Agent Run Contract 校验。

审查无 Critical。另有 MySQL DDL 半迁移恢复限制，已保留为后续专门工程问题，不在本 Change 静默扩大范围。
