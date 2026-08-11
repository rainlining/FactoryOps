# Change 验证记录：2026-08-10-define-vision-inspection-contract

## 验证元数据

- `status`: `partially-verified`
- `verified_at`: `2026-08-10 Asia/Shanghai（仅设计工件）`
- `verified_by`: `Codex`

## 当前阶段

本 Change 已通过 design review 和 Learning Preflight，正在执行 Stage 1。Executable Schema、vision-service fixture、semantic validator 和负向 fixtures 已实现；Stage 2 的 Fake 正向 fixture、recorded 外层示例和结果关系分类尚未开始。

## Stage 1 TDD 证据

### RED 1：Schema 尚不存在

```text
Command: python -m unittest contracts.vision_inspection.tests.test_validator -v
Actual: FileNotFoundError 指向 contracts/vision_inspection/v1.0/schema.json
Result: EXPECTED FAIL
```

### GREEN 1：合法 Vision Result

```text
Tests: 1
Result: PASS
```

### RED 2：Semantic Validator 尚不存在

```text
Actual: ModuleNotFoundError: contracts.vision_inspection.validator
Result: EXPECTED FAIL
```

### GREEN 2：精确版本与判断一致性

```text
Tests: 3
Result: PASS
```

### RED 3：Schema 错误路径过于宽泛

```text
Expected: $.model / $.ground_truth / $.recommended_action
Actual: $
Failures: 3
Result: EXPECTED FAIL
```

### GREEN 3：严格字段与可定位错误

```text
Tests: 6
Result: PASS
```

### TDD 修正：有限数值

```text
RED: NaN 被错误分类为 inconsistent_anomaly_decision
GREEN: NaN 被分类为 non_finite_number，path=$.observation.anomaly_score
Final tests: 7
Result: PASS
```

### Stage 1 完整验证

```text
Command: python -m unittest discover -s contracts/vision_inspection/tests -v
Actual: Ran 7 tests
Result: PASS

Command: python -m compileall -q contracts
Result: PASS

Command: python -m json.tool contracts/vision_inspection/v1.0/schema.json
Result: PASS

Command: git diff --check
Result: PASS

dataset changes: 0
```

## 设计阶段范围检查

- [x] proposal、spec、design 和 learning preflight 完成一致性检查。
- [x] 项目所有者批准双重身份、来源/重放分离、精确版本支持和统一模型字段设计。
- [x] 确认未创建 Vision、Java、Kafka、数据库或 Agent 运行时代码。
- [x] 项目所有者 review 并确认更新后的书面 OpenSpec 工件。
- [x] 项目所有者通过身份、来源/重放和精确版本三个 Preflight 场景。

实际设计检查结果：

```text
required_design_artifacts=True
change_name_valid=True
deep_level_declared=True
governance_dependency_declared=True
vision_service_out_of_scope=True
ground_truth_isolation_specified=True
version_and_conflict_paths_present=True
result_identity_separated=True
origin_and_delivery_separated=True
exact_version_support=True
fake_model_required=True
owner_task_and_failure_exercise_present=True
three_apply_stages=True
no_runtime_code=True
FAILED_COUNT=0
NON_DOC_CONFIG_FILE_COUNT=0
```

2026-08-11 在项目所有者批准关键设计决定后重新执行一致性检查：

```text
change_name_valid=True
status_design_reviewed=True
result_id_present=True
inspection_and_result_separated=True
origin_kinds_limited=True
recorded_outside_result=True
exact_version_support=True
fake_model_required=True
duplicate_uses_result_id=True
owner_decisions_recorded=True
no_runtime_files=True
contradiction_or_placeholder_hits=0
```

实施计划自审：

```text
implementation_stages=4
implementation_tasks=9
placeholder_hits=0
python_module_paths_valid=True
public_interface_names_consistent=True
all_spec_requirements_mapped=True
dataset_in_scope=False
runtime_service_scaffold_in_scope=False
```

## 未来验证范围

- Schema 正向与负向测试；
- 跨字段不变量测试；
- major/minor compatibility tests；
- fake、recorded、vision-service fixtures；
- 所有者修改任务；
- failure/debug exercise。

## 验收状态

- 技术验收：`pending`
- Code Walkthrough：`pending`
- 所有者修改任务：`pending`
- Failure/Debug Exercise：`pending`
- Learning Gate：`pending`
- Change 最终状态：`learning-preflight-passed`
