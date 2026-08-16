# Change 验证：2026-08-16-define-agent-task-contract

## 状态

- `status`: `technically-verified`
- `stacked_base`: `d6b4ca8338c97f05e2413982e40f26aa66864f71`
- `verified_implementation_head`: `4d9500189c073a0cfbc4ad3d475cfb072ebee5bc`
- Learning Gate：未开始

## TDD 与审查

1. RED：首次运行新测试因 `contracts.agent_task.validator` 不存在而收集失败。
2. 初版 GREEN：15 passed；Ruff 发现 1 个简化规则和 2 个格式文件，修复后通过。
3. 提交前语义复查发现 FAILED Task 仍可声明 retryable、非 PENDING 可缺 reason；补测试并修复。
4. 独立审查发现 1 Important：相同 dispatch key、不同 task_id 被误判 distinct；以 `4d95001` 修复，并补四类 type/role 全覆盖。

## 最终命令与结果

```powershell
python -m ruff check contracts/agent_task
python -m ruff format --check contracts/agent_task
python -m pytest contracts/agent_task/tests -q
python -m pytest contracts -q
```

结果：Ruff 通过；Task `22 passed`；全仓 Contract `97 passed`。

```powershell
cd services/agent-service
python -m pytest -q
python -m ruff check .
python -m ruff format --check .
```

结果：真实 MySQL/Kafka Testcontainers，`75 passed in 99.81s`；Ruff 通过；29 files formatted。

```powershell
cd backend/business-service
mvn verify -q
```

结果：退出码 0；27 unit + 38 integration = 65 tests，0 failures/errors/skipped。

```powershell
git diff --check d6b4ca8..HEAD
git status --short --branch
```

结果：通过；提交前工作树干净。未读取、修改或提交 `dataset/`。

## 审查结果与限制

- Critical：0；Important：1，已修复；剩余 Minor：0。
- Contract 不实现数据库唯一约束、依赖存在/同 Run/环检查、乐观锁或调度 ownership。
- `created_by_execution_id` 的 Coordinator role、终态 Execution 状态须由后续应用/持久化层跨对象校验。
- Task failure 的 non-retryable 是聚合终态；具体 Execution failure 仍保留自己的 recoverability。
