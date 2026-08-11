# Vision Inspection Contract 1.0

本文说明 FactoryOps 的视觉质检结果边界。它面向结果 Producer（生产者）和 Consumer（消费者），不是 Vision Service、Java 业务服务或 Evaluation Harness 的实现说明。

## Contract 负责什么

Contract 冻结一份视觉质检结果的：

- 业务质检身份 `inspection_id` 与不可变结果身份 `result_id`；
- 输入图像引用及 SHA-256；
- 原始生产者和模型 provenance（来源信息）；
- 异常分数、判断阈值和最终布尔结论；
- 可选 Artifact 引用；
- 产生时间和推理耗时；
- 精确版本与失败行为。

Contract 不负责判断图像的 ground truth（真实标签），也不允许 Vision Producer 决定复检、报废、冻结批次或停线等业务动作。

## 完整结果示例

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

## Consumer 校验

```python
from contracts.vision_inspection.validator import validate_result

validate_result(payload, supported_versions=("1.0",))
```

Consumer 必须明确列出自己支持的精确版本。只支持 `1.0` 时，必须拒绝 `1.1`，不能因为 major version 相同就静默接收。

校验顺序是：版本支持 → JSON Schema → 有限数值 → `is_anomaly == (anomaly_score >= decision_threshold)`。失败时抛出 `VisionContractValidationError`，其中的 `issues` 提供稳定错误代码和 JSON path。

## Fake 与 Recorded

- `origin.kind = "fake"`：结果最初由测试替身产生，仍必须保留 producer 和 model provenance。
- `input_mode = "recorded"`：外层运行环境正在重新输入一份历史结果，不是 Vision Result 的原始来源。

Recorded replay 不得把内部 `origin.kind` 改写为 `recorded`，否则相同 `result_id` 会出现内容冲突，并丢失原始生产者信息。外层示例见 `fixtures/examples/recorded-replay-envelope.json`。

## 两份结果的关系

`classify_result_relation(first, second)` 会先验证两份结果，再返回：

| 返回值 | 含义 |
|---|---|
| `duplicate-identical` | `result_id` 相同且规范化内容相同 |
| `duplicate-conflicting` | `result_id` 相同但内容不同 |
| `same-inspection-new-result` | `inspection_id` 相同但 `result_id` 不同 |
| `unrelated-result` | 两种身份都不同 |

规范化会排序 JSON object 的 key，因此仅字段顺序不同不构成冲突。相同 `result_id` 的内容冲突必须优先报告，不能被不同 `inspection_id` 掩盖。

## 测试

在仓库根目录运行：

```powershell
python -m unittest discover -s contracts/vision_inspection/tests -v
python -m json.tool contracts/vision_inspection/v1.0/schema.json > $null
```

本目录只包含 Contract、fixtures、校验与测试，不包含 Vision、Java、Kafka、数据库或 Agent Runtime。
