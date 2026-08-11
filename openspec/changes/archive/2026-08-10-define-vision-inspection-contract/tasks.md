# Vision Inspection Contract Implementation Plan

> **执行要求：** 后续实施必须使用 `superpowers:test-driven-development`，逐项完成本文件的 checkbox。Deep Change 每个 Stage 结束后必须停下来 review，未经项目所有者确认不得进入下一 Stage。

**目标：** 建立可执行的 Vision Inspection Contract 1.0、统一的 fake/vision fixtures、精确版本检查、跨字段校验及结果重复/冲突分类能力。

**架构：** JSON Schema Draft 2020-12 负责字段类型、required、枚举、格式与未知字段拒绝；Python semantic validator 负责精确版本选择、有限数值、`is_anomaly == (score >= threshold)` 和两份结果之间的关系分类。Vision Result 保持不可变，recorded 只出现在独立的外层示例中。

**技术栈：** JSON Schema Draft 2020-12、Python 3.10.18、jsonschema 4.26.0、Python `unittest`。

**设计确认：** 项目所有者已确认更新后的 proposal、spec 与 design；编码仍需先通过 Stage 0 Learning Preflight。

## 全局约束

- Change ID 保持 `2026-08-10-define-vision-inspection-contract`；日期表示首次建立日期。
- 不创建 Vision Service、Java Service、Kafka、数据库或 Agent Runtime。
- `inspection_id` 表示业务质检；`result_id` 表示不可变视觉结果。
- `origin.kind` 只允许 `vision-service` 或 `fake`；recorded 放在外层上下文。
- Fake 与真实结果都必须包含 producer、model 和 timing 信息。
- Consumer 只接受明确列出的精确版本；未知 major、未知 minor 和未知字段都拒绝。
- Evaluation ground truth、业务严重程度和推荐动作不得进入 Vision Result。
- `dataset/` 不属于本 Change，不得修改或提交。

## 计划文件结构

```text
contracts/
├── __init__.py
└── vision_inspection/
    ├── README.md
    ├── __init__.py
    ├── validator.py
    ├── v1.0/
    │   └── schema.json
    ├── fixtures/
    │   ├── valid/
    │   │   ├── vision-service-result.json
    │   │   └── fake-result.json
    │   ├── invalid/
    │   │   ├── anomaly-score-out-of-range.json
    │   │   ├── anomaly-decision-conflict.json
    │   │   ├── fake-result-without-model.json
    │   │   ├── ground-truth-leak.json
    │   │   ├── unknown-field.json
    │   │   └── unsupported-version.json
    │   └── examples/
    │       └── recorded-replay-envelope.json
    └── tests/
        ├── __init__.py
        └── test_validator.py
```

`validator.py` 对外只暴露：

```python
validate_result(payload: Mapping[str, object], supported_versions: Collection[str] = ("1.0",)) -> None
canonicalize_result(payload: Mapping[str, object]) -> bytes
classify_result_relation(existing: Mapping[str, object], incoming: Mapping[str, object]) -> ResultRelation
```

`ResultRelation` 的值固定为：

```text
duplicate-identical
duplicate-conflicting
same-inspection-new-result
unrelated-result
```

校验失败统一抛出 `VisionContractValidationError`，并提供结构化 `issues`；每个 issue 至少包含 `code`、`path`、`message`。

---

## Stage 0：Learning Preflight

### Task 0：确认编码前心智模型

**Files:**
- Modify: `openspec/changes/2026-08-10-define-vision-inspection-contract/learning.md`
- Modify: `openspec/changes/2026-08-10-define-vision-inspection-contract/verification.md`

**Interfaces:**
- Consumes: 已批准的 proposal、spec 和 design。
- Produces: `preflight_status: passed`，作为 Stage 1 编码许可。

- [x] **Step 0.1：项目所有者解释身份边界**

项目所有者用自己的话解释：为什么 `inspection_id` 与 `result_id` 不能混为一个身份，以及同一 inspection 下两个不同 result 为什么不自动构成冲突。

- [x] **Step 0.2：项目所有者解释来源边界**

项目所有者解释：为什么 recorded 不改写 `origin.kind`，以及改写后如何导致相同 `result_id` 被误判为内容冲突。

- [x] **Step 0.3：项目所有者解释版本策略**

项目所有者解释：为什么严格未知字段检查与“旧 Consumer 自动忽略 1.1 新字段”互相矛盾，以及本 Change 为什么选择精确版本支持。

- [x] **Step 0.4：记录 Preflight 结果并停下来 review**

只有上述解释达到“能够依据场景说明设计原因”时，才把 `learning.md` 更新为：

```text
preflight_status: passed
```

本步骤不创建 commit；未通过时继续讲解，不开始 Stage 1。

---

## Stage 1：Executable Schema 与 Semantic Validation

### Task 1：建立严格的 1.0 JSON Schema

**Files:**
- Create: `contracts/__init__.py`
- Create: `contracts/vision_inspection/v1.0/schema.json`
- Create: `contracts/vision_inspection/fixtures/valid/vision-service-result.json`
- Create: `contracts/vision_inspection/tests/__init__.py`
- Create: `contracts/vision_inspection/tests/test_validator.py`

**Interfaces:**
- Consumes: Vision Inspection Contract 1.0 字段与边界。
- Produces: Draft 2020-12 Schema；合法 vision-service fixture。

- [x] **Step 1.1：添加会因 Schema 尚不存在而失败的测试**

在 `test_validator.py` 中先添加：

```python
import json
import unittest
from pathlib import Path

from jsonschema import Draft202012Validator, FormatChecker

ROOT = Path(__file__).resolve().parents[1]


class VisionInspectionSchemaTest(unittest.TestCase):
    def test_vision_service_fixture_matches_v1_schema(self) -> None:
        schema = json.loads((ROOT / "v1.0" / "schema.json").read_text(encoding="utf-8"))
        payload = json.loads(
            (ROOT / "fixtures" / "valid" / "vision-service-result.json").read_text(encoding="utf-8")
        )
        Draft202012Validator(schema, format_checker=FormatChecker()).validate(payload)
```

- [x] **Step 1.2：运行测试并确认失败原因正确**

Run:

```powershell
python -m unittest contracts.vision_inspection.tests.test_validator -v
```

Expected: FAIL，错误是 `schema.json` 或 fixture 不存在，而不是测试导入或语法错误。

- [x] **Step 1.3：添加最小合法 fixture**

Fixture 必须包含以下实际结构，不使用省略字段：

```json
{
  "contract_version": "1.0",
  "inspection_id": "inspection-00731",
  "result_id": "result-1001",
  "input": {
    "image_uri": "artifact://images/sheet-metal-00731",
    "sha256": "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"
  },
  "origin": {
    "kind": "vision-service",
    "producer_name": "factoryops-vision",
    "producer_version": "0.1.0"
  },
  "model": {
    "name": "sheet-metal-anomaly-detector",
    "version": "vision-v1"
  },
  "observation": {
    "is_anomaly": true,
    "anomaly_score": 0.93,
    "decision_threshold": 0.6
  },
  "artifacts": {
    "defect_mask": {
      "uri": "artifact://masks/00731",
      "media_type": "image/png"
    }
  },
  "timing": {
    "produced_at": "2026-08-10T10:00:00Z",
    "inference_ms": 37
  }
}
```

- [x] **Step 1.4：实现严格 Schema**

Schema 必须：

- 使用 `$schema: https://json-schema.org/draft/2020-12/schema`；
- 对每个 object 使用 `additionalProperties: false`；
- 要求示例中的全部核心字段；
- `contract_version` 使用 `const: "1.0"`；
- `origin.kind` 枚举仅为 `vision-service`、`fake`；
- score/threshold 为 `[0,1]` number；
- `inference_ms` 为非负整数；
- SHA-256 使用 `^[0-9a-f]{64}$`；
- Artifact 内容只允许 URI 与媒体类型，不允许二进制字段。

- [x] **Step 1.5：运行测试确认通过**

Run:

```powershell
python -m unittest contracts.vision_inspection.tests.test_validator -v
```

Expected: 1 test PASS。

### Task 2：实现统一校验错误与跨字段不变量

**Files:**
- Create: `contracts/vision_inspection/__init__.py`
- Create: `contracts/vision_inspection/validator.py`
- Modify: `contracts/vision_inspection/tests/test_validator.py`
- Create: `contracts/vision_inspection/fixtures/invalid/anomaly-decision-conflict.json`
- Create: `contracts/vision_inspection/fixtures/invalid/unsupported-version.json`

**Interfaces:**
- Consumes: `v1.0/schema.json`。
- Produces: `validate_result(...)`、`ValidationIssue`、`VisionContractValidationError`。

- [x] **Step 2.1：先添加跨字段与精确版本失败测试**

测试必须断言：

```python
with self.assertRaises(VisionContractValidationError) as caught:
    validate_result(conflicting_payload)
self.assertEqual(caught.exception.issues[0].code, "inconsistent_anomaly_decision")
self.assertEqual(caught.exception.issues[0].path, "$.observation.is_anomaly")

with self.assertRaises(VisionContractValidationError) as caught:
    validate_result(version_1_1_payload, supported_versions=("1.0",))
self.assertEqual(caught.exception.issues[0].code, "unsupported_contract_version")
self.assertEqual(caught.exception.issues[0].path, "$.contract_version")
```

- [x] **Step 2.2：运行测试确认因 API 尚不存在而失败**

Run:

```powershell
python -m unittest contracts.vision_inspection.tests.test_validator -v
```

Expected: FAIL，错误指向无法导入 validator API。

- [x] **Step 2.3：实现最小 public API**

`validator.py` 必须定义：

```python
@dataclass(frozen=True)
class ValidationIssue:
    code: str
    path: str
    message: str


class VisionContractValidationError(ValueError):
    def __init__(self, issues: Sequence[ValidationIssue]) -> None:
        self.issues = tuple(issues)
        super().__init__("; ".join(f"{issue.path}: {issue.message}" for issue in self.issues))
```

`validate_result` 按以下固定顺序执行：

1. 读取 `contract_version`；
2. 检查它是否在调用者传入的 `supported_versions` 中；
3. 加载对应精确版本 Schema；
4. 将 JSON Schema errors 转为稳定的 `schema_validation_failed` issue；
5. 使用 `math.isfinite` 检查 score 与 threshold；
6. 检查 `is_anomaly == (anomaly_score >= decision_threshold)`。

- [x] **Step 2.4：运行测试确认通过**

Run:

```powershell
python -m unittest contracts.vision_inspection.tests.test_validator -v
```

Expected: vision fixture、冲突判断和 unsupported 1.1 tests 全部 PASS。

### Task 3：覆盖严格边界和 Ground Truth 隔离

**Files:**
- Modify: `contracts/vision_inspection/tests/test_validator.py`
- Create: `contracts/vision_inspection/fixtures/invalid/fake-result-without-model.json`
- Create: `contracts/vision_inspection/fixtures/invalid/ground-truth-leak.json`
- Create: `contracts/vision_inspection/fixtures/invalid/unknown-field.json`

**Interfaces:**
- Consumes: `validate_result(...)`。
- Produces: Fake model、未知字段和答案泄漏的回归保护。

- [x] **Step 3.1：添加三个负向 fixture tests**

测试分别断言以下字段路径被拒绝：

```text
fake-result-without-model.json → $.model
ground-truth-leak.json         → $.ground_truth
unknown-field.json             → $.recommended_action
```

- [x] **Step 3.2：运行测试并确认至少一个测试先失败**

如果当前严格 Schema 已让全部新测试直接通过，临时复制合法 payload 并加入一个尚未被 Schema 拒绝的嵌套未知字段 `observation.explanation`，确认测试先失败，再将相应 object 的 `additionalProperties: false` 补齐。

Run:

```powershell
python -m unittest contracts.vision_inspection.tests.test_validator -v
```

- [x] **Step 3.3：完成最小 Schema 修正并运行全套测试**

Expected: 全部测试 PASS，且错误 issue 含稳定 JSON path。

- [x] **Step 3.4：提交 Stage 1 并停下来 review**

只暂存 Stage 1 文件与本 Change 记录，明确排除 `dataset/`：

```powershell
git add -- contracts/vision_inspection openspec/changes/2026-08-10-define-vision-inspection-contract
git commit -m "add executable vision inspection contract"
```

提交前运行：

```powershell
python -m unittest contracts.vision_inspection.tests.test_validator -v
git diff --cached --name-only
```

Codex 提交并推送后停止，提供 Stage 1 Code Walkthrough，等待项目所有者批准 Stage 2。

- [x] **Step 3.5：项目所有者完成 Stage 1 diff review**

Review 证据（2026-08-11）：

- 能沿 `validate_result(...)` 说明版本检查、Schema 校验和跨字段语义校验的顺序；
- 能判断嵌套未知字段的精确路径 `$.observation.explanation`；
- 能解释 `anomaly_score`、`decision_threshold`、`is_anomaly` 的关系和等于阈值的边界；
- 能说明负向 fixture test 如何阻止 `recommended_action` 被意外放行；
- 能说明只做 Schema 校验会让跨字段矛盾进入下游；
- 项目所有者已明确接受 Stage 1。

Stage 2 尚未获实施批准；此处不勾选任何 Stage 2 任务。

---

## Stage 2：Fixtures、版本与结果关系

### Task 4：加入 Fake Result 和 Recorded Replay 示例

**Files:**
- Create: `contracts/vision_inspection/fixtures/valid/fake-result.json`
- Create: `contracts/vision_inspection/fixtures/examples/recorded-replay-envelope.json`
- Modify: `contracts/vision_inspection/tests/test_validator.py`

**Interfaces:**
- Consumes: `validate_result(...)`。
- Produces: 与真实结果同形的 fake fixture；不改写 Vision Result 的 recorded envelope 示例。

- [x] **Step 4.1：添加 Fake shape 与 recorded immutability tests**

测试必须断言：

```python
validate_result(fake_payload)
self.assertEqual(fake_payload["origin"]["kind"], "fake")
self.assertIn("model", fake_payload)

validate_result(recorded_envelope["vision_result"])
self.assertEqual(recorded_envelope["input_mode"], "recorded")
self.assertNotEqual(recorded_envelope["vision_result"]["origin"]["kind"], "recorded")
```

- [x] **Step 4.2：运行测试确认 fixture 尚不存在导致失败**

- [x] **Step 4.3：添加最小 fixtures 并确认测试通过**

Recorded envelope 只用于说明外层关系，不纳入 Vision Result Schema。

### Task 5：实现结果规范化和关系分类

**Files:**
- Modify: `contracts/vision_inspection/validator.py`
- Modify: `contracts/vision_inspection/tests/test_validator.py`

**Interfaces:**
- Consumes: 两份通过 `validate_result` 的 payload。
- Produces: `canonicalize_result(...)` 与 `classify_result_relation(...)`。

- [x] **Step 5.1：先添加四种关系的失败测试**

覆盖：

```text
同 result_id、仅 JSON key 顺序不同    → duplicate-identical
同 result_id、anomaly_score 不同      → duplicate-conflicting
同 inspection_id、不同 result_id      → same-inspection-new-result
inspection_id 与 result_id 都不同     → unrelated-result
```

- [x] **Step 5.2：实现规范化**

```python
json.dumps(
    payload,
    sort_keys=True,
    separators=(",", ":"),
    ensure_ascii=False,
    allow_nan=False,
).encode("utf-8")
```

- [x] **Step 5.3：实现固定优先级的关系分类**

1. 两份输入先分别通过 `validate_result`；
2. `result_id` 相同且 canonical bytes 相同 → `duplicate-identical`；
3. `result_id` 相同且 canonical bytes 不同 → `duplicate-conflicting`；
4. `inspection_id` 相同 → `same-inspection-new-result`；
5. 否则 → `unrelated-result`。

- [x] **Step 5.4：运行全套测试并提交 Stage 2**

```powershell
python -m unittest contracts.vision_inspection.tests.test_validator -v
git add -- contracts/vision_inspection openspec/changes/2026-08-10-define-vision-inspection-contract
git commit -m "add vision contract fixtures and replay semantics"
```

Codex 推送后停止，讲解 Fake/recorded 边界与关系分类调用链，等待项目所有者批准 Stage 3。

- [x] **Step 5.5：项目所有者完成 Stage 2 diff review**

Review 证据（2026-08-11）：

- 能说明相同 `result_id`、不同内容必须判为 `duplicate-conflicting`；
- 能说明 JSON object 字段顺序不同不构成内容冲突；
- 能说明非法 Contract 必须先拒绝，不能参与结果关系分类；
- 能区分新增关系测试与既有负向回归测试的职责；
- 能解释 recorded replay 不得改写原始 `origin.kind`；
- 能说明 fake 结果保留 model provenance 对可解释性和复现的意义；
- 项目所有者已明确接受 Stage 2。

Stage 3 尚未获实施批准；此处不勾选任何 Stage 3 任务。

---

## Stage 3：文档、所有者修改与故障实验

### Task 6：建立 Contract 使用说明和完整验证

**Files:**
- Create: `contracts/vision_inspection/README.md`
- Modify: `openspec/changes/2026-08-10-define-vision-inspection-contract/verification.md`

**Interfaces:**
- Consumes: Schema、validator、fixtures 和 tests。
- Produces: Producer/Consumer 使用说明与真实验证证据。

- [x] **Step 6.1：编写 README**

README 必须包含：

- Contract 边界和非目标；
- 完整字段示例；
- `validate_result` 使用示例；
- 精确版本支持示例；
- Fake 与 recorded 的区别；
- 四种 ResultRelation；
- 测试命令。

- [x] **Step 6.2：运行完整验证并记录实际输出**

```powershell
python -m unittest discover -s contracts/vision_inspection/tests -v
python -m json.tool contracts/vision_inspection/v1.0/schema.json > $null
```

不得在执行前将结果填写为 PASS。

### Task 7：项目所有者亲自修改任务

**Files:**
- Create by owner: `contracts/vision_inspection/fixtures/invalid/anomaly-score-out-of-range.json`
- Modify by owner: `contracts/vision_inspection/tests/test_validator.py`

**Interfaces:**
- Consumes: `validate_result(...)` 和现有 fixture loader。
- Produces: `1.01` 被拒绝、`1.0` 被接受的边界测试。

- [x] **Step 7.1：项目所有者创建非法 fixture**

从合法 fake fixture 复制，保持其他字段不变，仅将：

```json
"anomaly_score": 1.01
```

- [x] **Step 7.2：项目所有者添加测试**

测试必须检查异常 issue 的 path 为：

```text
$.observation.anomaly_score
```

并增加或保留 `anomaly_score = 1.0` 的合法边界断言。

- [x] **Step 7.3：项目所有者运行测试并解释结果**

```powershell
python -m unittest contracts.vision_inspection.tests.test_validator -v
```

### Task 8：Failure/Debug Exercise 与最终 Learning Gate

**Files:**
- Modify during exercise: `contracts/vision_inspection/validator.py`
- Restore after exercise: `contracts/vision_inspection/validator.py`
- Modify: `openspec/changes/2026-08-10-define-vision-inspection-contract/learning.md`
- Modify: `openspec/changes/2026-08-10-define-vision-inspection-contract/verification.md`

**Interfaces:**
- Consumes: threshold equality test 和 conflict fixture。
- Produces: 故障证据、恢复证据、Code Walkthrough 和 Learning Gate 结果。

- [x] **Step 8.1：确认正常实现的边界测试通过**

使用 `anomaly_score == decision_threshold` 且 `is_anomaly == true` 的 fixture，确认 `>=` 行为通过。

- [x] **Step 8.2：项目所有者临时注入故障**

把 validator 中的：

```python
score >= threshold
```

临时改为：

```python
score > threshold
```

- [x] **Step 8.3：运行测试并定位失败**

Expected: threshold equality test FAIL；项目所有者说明失败如何证明 Java/Python 等 Consumer 不能各自发明边界规则。

- [x] **Step 8.4：恢复正确实现并重新验证**

恢复 `>=`，运行完整测试，确认全部通过。

- [x] **Step 8.5：Codex 提供真实 Code Walkthrough**

必须沿真实文件说明：Schema 入口、版本分派、Schema errors 转换、跨字段判断、Fake/recorded fixtures、关系分类和失败测试。

- [x] **Step 8.6：完成 Learning Gate 与最终提交**

只有项目所有者完成修改、故障实验、Walkthrough review 和最终 diff review 后，才能将 Change 标记为 `completed` 并归档。

最终提交前运行：

```powershell
python -m unittest discover -s contracts/vision_inspection/tests -v
git diff --check
git status --short
```

最终提交信息：

```text
complete vision inspection contract learning gate
```

## 需求覆盖检查

| 规格要求 | 覆盖任务 |
|---|---|
| 双重稳定身份 | Task 1、Task 5 |
| 输入图像与原始来源 | Task 1、Task 4 |
| Score/threshold 数值和一致性 | Task 1、Task 2、Task 8 |
| 所有结果具有 model/producer provenance | Task 1、Task 3、Task 4 |
| 可选 Artifact 引用且不内嵌二进制 | Task 1、Task 3 |
| 禁止业务决策与 Ground Truth | Task 3 |
| 精确版本支持 | Task 2 |
| 重复、冲突与同质检多结果 | Task 5 |
| Score 不跨模型直接比较 | README 文档与后续业务策略边界；本 Change 不实现比较逻辑 |
| 所有者修改和 Failure Exercise | Task 7、Task 8 |
