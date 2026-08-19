# Verification

状态：`review-handoff-ready`。

基线：`e8094d77716b175e2a5040daa2bd85711edaf5a4`（`codex/persist-risk-decision`）。

实际验证：

- `python -m pytest -q contracts`：133 passed。
- `python -m pytest -q contracts/coordinator_fusion/tests`：9 passed。
- Agent Service 全量测试：161 passed in 216.28s。
- Java `mvn verify -q`：退出码 0；20 个 XML 报告、65 tests、0 failures、0 errors、0 skipped。
- `python -m ruff check contracts/coordinator_fusion`：通过。
- `python -m ruff format --check contracts/coordinator_fusion`：4 files already formatted。
- `python -m json.tool contracts/coordinator_fusion/v1.0.0/schema.json`：通过。
- `git diff --check`：通过。
- `git status --short -- dataset`：无输出，dataset 未修改。

验证覆盖：源 Recommendation identity 一致性、跨 Run 拒绝、角色覆盖、候选 rank、授权状态、ground-truth 防泄漏、非有限数拒绝、冲突标志、canonical 顺序/数值归一化，以及 identical/conflicting/distinct 关系分类。

已知限制：Contract 层只能验证 payload 自洽的 `coordinator_execution_id` 与 fusion key，不能替代数据库事实校验；本 Change 不实现持久化、Risk Gate、Approval 或业务动作。

独立子 Agent 首审发现 1 个 Important：候选的 supporting/opposing roles 未绑定源 Recommendation action，可能伪造共识。已增加 action attribution 校验与负向测试；同时补充双 Specialist 降级输入、missing role 归属拒绝和无效源 Contract 的 Fusion 错误包装。修复后局部 9 passed、全 Contract 133 passed、Agent 161 passed、Java 65/65；等待同一子 Agent 复审。
