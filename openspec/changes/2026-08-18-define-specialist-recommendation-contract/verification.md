# Verification

- Specialist Contract 局部：实现移交时 `16 passed in 0.15s`；Review Owner 修改后 `17 passed in 0.12s`。覆盖三角色、固定 key 向量、严格 details、边界、NaN/Infinity、duplicate relation、ground truth/expected action、Production 64 个唯一 affected order refs 上界和稳定错误路径。
- 全 Contract：Review 收尾时 `116 passed in 0.55s`。
- stacked Agent Service 全量：`144 passed in 252.56s`。
- Java `backend/business-service mvn verify -q`：exit 0；20 份 XML，`65 tests, 0 failures/errors/skipped`。
- `python -m json.tool` Schema 解析通过；新 Contract Ruff check/format 通过，5 files formatted。
- `git diff --check` 通过；Change diff 与 `dataset/` 无交集。
- implementation commit：`8960d19`；最终 handoff commit 以远端分支 HEAD 为准。

Review/Learning 会话实际运行 Owner 测试：`pytest -q contracts/specialist_recommendation/tests/test_validator.py -k production_affected_order_refs_accept_unique_upper_bound`，结果 `1 passed, 16 deselected in 0.11s`。Failure exercise 使用合法 SLA fixture 注入顶层 `expected_action=HOLD_BATCH`，实际得到 `schema_validation_failed $.expected_action`。Owner 修改由 Codex 代做，不能算作项目所有者亲自完成。

RED 阶段共 5 项失败：角色 mismatch 路径不稳定，Infinity 被 Schema 先分类。修复为版本后先执行窄 finite/role preflight，再进入 Schema；最终局部 16 项通过。独立审查修正文案：单 Recommendation 无法校验与 Execution 的跨对象时间顺序，v1 只校验 generated_at UTC 形状。无未处理 Critical/Important。
