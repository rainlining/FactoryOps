# Verification

状态：`technically-verified`，等待独立代码审查后进入 `review-handoff-ready`。

基线：`e8094d77716b175e2a5040daa2bd85711edaf5a4`（`codex/persist-risk-decision`）。

实际验证：

- `python -m pytest -q contracts`：130 passed。
- `python -m pytest -q contracts/coordinator_fusion/tests`：6 passed。
- Agent Service 全量测试：161 passed in 301.63s。
- Java `mvn verify -q`：退出码 0；20 个 XML 报告、65 tests、0 failures、0 errors、0 skipped。
- `python -m ruff check contracts/coordinator_fusion`：通过。
- `python -m ruff format --check contracts/coordinator_fusion`：4 files already formatted。
- `python -m json.tool contracts/coordinator_fusion/v1.0.0/schema.json`：通过。
- `git diff --check`：通过。
- `git status --short -- dataset`：无输出，dataset 未修改。

验证覆盖：源 Recommendation identity 一致性、跨 Run 拒绝、角色覆盖、候选 rank、授权状态、ground-truth 防泄漏、非有限数拒绝、冲突标志、canonical 顺序/数值归一化，以及 identical/conflicting/distinct 关系分类。

已知限制：Contract 层只能验证 payload 自洽的 `coordinator_execution_id` 与 fusion key，不能替代数据库事实校验；本 Change 不实现持久化、Risk Gate、Approval 或业务动作。
