# Change 验证：2026-08-16-define-agent-execution-contract

## 状态

- `status`: `technically-verified`
- `verified_head`: `aed474706f795e1702ae2505d88a579a507117dd`
- 技术验收：通过
- Learning Gate：未开始；不属于本实现会话

## TDD 与审查证据

1. 首次运行新测试时因 `contracts.agent_execution.validator` 不存在而收集失败，证明测试先于实现。
2. 初版实现后 14 tests passed；Ruff 报告 1 个简化规则和 3 个格式文件，随后修复。
3. 技术复查发现 key 未包含 Task 会导致同一角色多个 Task 碰撞；提交前把 Task 纳入规范摘要。
4. 独立审查发现 2 个 Important：快照时间可晚于 `updated_at`；下一 revision 可改写 `started_at`。新增测试并以 `aed4747` 修复。

## 最终验证命令与结果

```powershell
python -m ruff check contracts/agent_execution
python -m ruff format --check contracts/agent_execution
python -m pytest contracts/agent_execution/tests -q
python -m pytest contracts -q
```

结果：Ruff 通过；新 Contract `18 passed`；全部 Contract `75 passed`。

```powershell
cd services/agent-service
python -m pytest -q
python -m ruff check .
python -m ruff format --check .
```

结果：真实 MySQL/Kafka Testcontainers 运行，`75 passed in 116.93s`；Ruff check 通过；29 files already formatted。

```powershell
cd backend/business-service
mvn verify -q
```

结果：退出码 0；Surefire 27 tests，Failsafe 38 tests，共 65 tests，0 failures/errors/skipped。

```powershell
git diff --check f2fc6b7..HEAD
git status --short --branch
```

结果：通过；提交前工作树干净。`dataset/` 不在 feature worktree，未读取、修改或提交。

## 环境事件

首次容器回归因 Docker Desktop 未运行而失败，错误为缺少 `dockerDesktopLinuxEngine`。启动 Docker Desktop 并确认 `docker info` 成功后，完整重跑得到上述通过结果；该首次失败是环境前置条件，不是断言失败。

## 独立审查结果

- Critical：0。
- Important：2，均已修复。
- 剩余 Minor：0。
- 范围：只新增 Agent Execution Contract/OpenSpec；未接入数据库、Worker、LLM、Tool 或 Java API。

## 限制与剩余风险

- 跨记录唯一约束、乐观锁和事务由后续持久化 Change 实现。
- `recoverability=retryable` 是失败事实，不授权运行时自动重试。
- Task、Context、Artifact 和 Decision 只是引用；存在性由后续应用层验证。
- 仓库根目录用当前全局 Ruff 扫描会报告 18 个既有文件问题；新目录和 Agent Service 在各自项目上下文均通过。本 Change 未修改无关历史文件。

## Review/Learning 会话增量验证（2026-08-17）

- Codex 代做 Owner 修改：`failure.message` 上限 500 → 600；同步 Schema、README 和 600/601 边界测试。该代做不能计为项目所有者亲自完成。
- `python -m ruff check contracts/agent_execution`：通过。
- `python -m ruff format --check contracts/agent_execution`：6 files already formatted。
- `python -m pytest contracts/agent_execution/tests -q`：`19 passed in 0.32s`。
- `python -m pytest contracts -q`：`76 passed in 0.93s`。
- 故障实验：修改 `attempt` 并保留旧 key，实际得到 `execution_key_mismatch` 与 `$.identity.execution_key`；重算 key 后通过。
- `git diff --check`：通过；仅涉及当前 Contract、测试、README 和 Change 记录。
