# Human Approval Contract Implementation Plan

1. 先写 Contract 测试与 valid fixture，确认模块缺失 RED。
2. 实现 strict JSON Schema 与 validator/source binding/key/state invariants。
3. 实现 canonical bytes 和 relation classifier，覆盖合法 revision。
4. 运行局部与全量 Contract、Agent、Java、Ruff/JSON/diff/dataset 验证。
5. 更新 OpenSpec，提交后调用独立 Agent 审查；修复 Critical/Important 并复审推送。
