# Change 验证记录：<change-id>

## 验证元数据

- `status`: `not-run | partially-verified | technically-verified | accepted`
- `verified_at`: 由执行验证者填写实际时间
- `verified_by`: 项目所有者或 Codex

## 范围检查

- [ ] 实现只覆盖 proposal 的范围。
- [ ] 非目标没有被意外实现。
- [ ] 顶层规格、Change 规格、设计和任务不存在明显冲突。

## 验证命令与实际结果

每次执行追加记录，不预填虚构的 PASS：

```text
Command:
Expected:
Actual:
Result: PASS | FAIL
Evidence:
```

## 负向与失败验证

记录故障条件、执行方式、实际行为和恢复结果。

## Code Walkthrough 证据

列出真实文件、符号、调用顺序和相关测试；未实现时保持未完成状态。

## 已知限制与剩余风险

列出当前明确接受但尚未解决的限制，不使用模糊占位符。

## 验收状态

- 技术验收：`pending | passed`
- Code Walkthrough：`pending | passed | N/A`
- 所有者修改任务：`pending | passed | N/A`
- Failure/Debug Exercise：`pending | passed | N/A`
- Learning Gate：`pending | passed | N/A`
- Change 最终状态：`proposed | technically-verified | awaiting-learning-gate | completed`
