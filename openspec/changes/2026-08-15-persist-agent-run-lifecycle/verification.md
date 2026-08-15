# Verification：2026-08-15-persist-agent-run-lifecycle

## 当前状态

- `change_status`: `completed`
- `technical_verification`: `passed`
- `learning_gate`: `passed`

## 实际验证

在 2026-08-15 从对应目录执行：

| 范围 | 命令 | 结果 |
| --- | --- | --- |
| Python lint | `python -m ruff check src tests` | 通过 |
| Python format | `python -m ruff format --check src tests` | 通过 |
| Agent Service | `python -m pytest -q` | 51 passed |
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

多轮只读审查发现的 Important 均已修复并加入真实 MySQL 回归：

1. replay 幂等键的已存在分类提前到 lineage 校验之前；
2. 状态迁移在 SQL 写入前构造候选 snapshot 并执行 Agent Run Contract 校验。
3. original、replay 与 transition 均在业务校验前优先分类已提交的幂等键。
4. 三条路径均覆盖“首次查询未命中、并发赢家随后提交、当前请求在 INSERT 前失败”的竞态，并在失败出口重新查询赢家。

最终 Head `a415350` 的独立审查结论为 Ready：0 Critical、0 Important。另有 MySQL DDL 半迁移恢复和 transition history 更多防御性 CHECK 建议，均保留为后续独立工程问题，不阻塞当前规格。

## GitHub 推送状态

- 早期 Git HTTPS 连接曾超时；2026-08-15 重试成功。
- `main` 已从远端 `651228b` 推进到本地基线 `a5e0da6`。
- `codex/persist-agent-run-lifecycle` 已创建并跟踪同名远端分支。
- 本 handoff 状态提交后再次推送，并用远端引用核对最终 commit。
