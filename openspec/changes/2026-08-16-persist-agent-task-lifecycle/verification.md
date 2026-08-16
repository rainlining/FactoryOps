# 技术验证：2026-08-16-persist-agent-task-lifecycle

## 状态

- `status`: `technically-verified`
- `reviewed_implementation_head`: `f1c48f5`
- 环境：Windows、Python、Docker Desktop、MySQL 8.4 Testcontainers、Kafka Testcontainers、Java 17。

## TDD 证据

首次执行局部 pytest 时测试收集失败，错误为 `ModuleNotFoundError: factoryops_agent_service.task_lifecycle`，证明测试先于实现。首轮实现后 11 passed、2 failed；失败因终态夹具缺少既有 current Execution 与 completion/failure payload，修正夹具后 13 passed。补齐高风险与审查回归后最终局部结果为 `18 passed`。

## 最终命令与结果

```powershell
python -m pytest contracts -q
```

结果：`97 passed in 1.26s`。

```powershell
cd services/agent-service
python -m pytest -q
python -m ruff check src tests
python -m ruff format --check src tests
```

结果：`93 passed in 112.13s`；Ruff `All checks passed`；35 files already formatted。93 = 原 Agent 75 + Task persistence 18。

```powershell
cd backend/business-service
mvn verify -q
```

结果：exit code 0；Surefire + Failsafe 的 20 份 XML 汇总为 `65 tests, 0 failures, 0 errors, 0 skipped`。日志中的 broker unavailable、missing topic 和 migration failure 是已有负向测试的预期注入。

```powershell
git diff --check
git diff --name-only b39970f..HEAD | Select-String '^dataset/'
```

结果：无 whitespace error；无 `dataset/` 文件。

## 覆盖证据

- migration 003 和三张表真实创建；runner 从仅 001 的数据库有序升级且可重入。
- 创建 snapshot/dependencies/initial history 同事务；相同与冲突重投分类。
- 父 Run、缺失依赖、跨 Run 依赖均拒绝；合法依赖按顺序重建。
- 首次 RUNNING、retry attempt、SUCCEEDED、CANCELLED、终态保护与时钟回退。
- status/revision 并发测试最多一个赢家；stale revision 返回 concurrency conflict。
- initial/history 注入失败分别验证整单回滚和 snapshot 回滚。
- 人工破坏 role/type 快照后读取抛 `PersistenceIntegrityError`。

## 独立审查

发现并修复 2 个 Important：RUNNING→CANCELLED 重投误分类；completion/failure 残留列可能被重建忽略。另修复 transition request 在首次查询后发生并发提交时的二次读取分类。复审结果：0 Critical、0 Important；未发现阻塞 handoff 的 Minor。

## 限制与剩余风险

- Execution 表尚不存在，Execution ID 只有 Contract 校验、没有数据库 FK；后续独立 migration 必须补齐。
- 未实现 dispatch Worker、lease/claim、retry policy、Checkpoint/Resume 或跨 Task DAG 环检测。
- MySQL tests 使用短生命周期容器，尚无长时间运行与大规模索引性能基准。
- 本 Change stacked 在两个待 Learning Gate 的 Contract Change 上；上游 review commit 必须吸收后重验。

技术验收通过；学习与 Owner 接受尚未开始，因此不得归档或合并 `main`。
