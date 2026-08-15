# Verification：2026-08-15-define-agent-run-contract

## 当前状态

- `change_status`: `archived`
- `technical_verification`: `passed`
- `learning_gate`: `passed`

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

最终结果：56/56 通过，退出码 0。包含 Agent Run 21 个、Quality Incident Opened 18 个、Vision Inspection 17 个测试。

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
- 2026-08-15 首轮三次推送因无法连接 `github.com:443` 超时；网络恢复后重新执行 `git -c http.version=HTTP/1.1 push -u origin codex/define-agent-run-contract` 成功，feature branch 已发布。

## 最终 Diff Review

独立只读审查范围：`651228b9d71ee81e80e6a5030e4c49a50ec60f88..0dfe007c48710810c2ed94ecd09a0c6d93d89b20`。

审查发现并修复：

1. JSON Schema 接受 integer 语义的 `0.0`，旧 canonical bytes 却与 `0` 不同；现统一规范 integral float。
2. `anyOf` 错误原先只定位到 `status_reason`；现递归选择最具体叶级 Schema error。
3. 严格对象测试原先未递归覆盖 `$defs.statusReason`；现递归遍历所有 object schema。
4. Handoff、Owner 任务和真实 head 信息已同步。

修复提交：`662f20983e00a6aa4d6faea2eaf8b21a160d2a37`。修复后无 Critical 或 Important 遗留问题。

## 范围检查

- [x] 未创建数据库、Kafka 或 Agent Runtime。
- [x] 未修改 `dataset/`。
- [x] `git diff --check` 通过。
