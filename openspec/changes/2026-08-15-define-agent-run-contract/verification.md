# Verification：2026-08-15-define-agent-run-contract

## 当前状态

- `change_status`: `review-handoff-ready`
- `technical_verification`: `passed`
- `learning_gate`: `pending`

## 验证记录

### TDD RED 证据

1. `python -m unittest contracts.agent_run.tests.test_schema -v`
   - 结果：3 个测试按预期失败。
   - 原因：`v1.0.0/schema.json` 尚不存在。
2. `python -m unittest contracts.agent_run.tests.test_validator.AgentRunValidationTest -v`
   - 结果：按预期无法导入测试模块。
   - 原因：`contracts.agent_run.validator` 尚不存在。
3. `python -m unittest contracts.agent_run.tests.test_validator.AgentRunRelationTest -v`
   - 结果：按预期无法导入 relation symbols。
   - 原因：`canonicalize_run` 与 `classify_run_relation` 尚不存在。

### 局部 GREEN 证据

1. `python -m unittest contracts.agent_run.tests.test_schema -v`
   - 结果：3/3 通过。
2. `python -m unittest contracts.agent_run.tests.test_validator.AgentRunValidationTest -v`
   - 结果：12/12 通过。
3. `python -m unittest contracts.agent_run.tests.test_validator -v`
   - 结果：17/17 通过。

### Contract 全量回归

命令：

```powershell
python -m unittest discover -s contracts -p "test_*.py" -v
```

结果：55/55 通过，退出码 0。包含 Agent Run 20 个、Quality Incident Opened 18 个、Vision Inspection 17 个测试。

### Python 格式与静态检查

命令：

```powershell
python -m ruff check contracts/agent_run
python -m ruff format --check contracts/agent_run
```

结果：Ruff 检查全部通过；6 个 Python 文件均已格式化。

### Diff 验证

命令：

```powershell
git diff --check
```

结果：退出码 0，无空白错误。

## 已知限制

- JSON Schema 与单条 Validator 无法证明幂等键在数据库中唯一。
- 无法在不加载历史记录的情况下证明 replay 引用存在、类型正确或不存在跨记录循环。
- 本 Change 不验证状态迁移边，只验证当前快照的状态与时间组合。
- `revision` 的并发更新语义要由后续 MySQL Lifecycle Change 证明。

## 范围检查

- [x] 未创建数据库、Kafka 或 Agent Runtime。
- [x] 未修改 `dataset/`。
- [x] `git diff --check` 通过。
