# Verification

状态：`technically-verified`，等待独立子 Agent 审查。

## 实际验证

- `python -m pytest -q contracts`：`154 passed in 4.69s`。
- `python -m pytest -q contracts/human_approval/tests`：`19 passed`（Contract GREEN 阶段）。
- `python -m pytest -q services/agent-service/tests/test_human_approval_mysql.py`：`14 passed in 17.83s`。
- `python -m pytest -q services/agent-service/tests`：`217 passed in 604.92s`。
- `mvn -q -Dtest=HumanApprovalHttpIT test`：`11 tests`，0 failure/error。
- `mvn verify -q`：退出码 0；Surefire XML 共 `22 reports / 87 tests / 0 failures / 0 errors / 0 skipped`。
- 变更范围 Ruff check、Ruff format check、v1.1 JSON schema parse 与 `git diff --check` 通过。
- `git status --short -- dataset` 无输出。

## 关键证据

- Contract v1.1 缺失/替换 incident、Run 错绑与 relation 测试。
- Agent 真实 MySQL 验证 v1.1 current/history、typed incident 漂移拒绝、migration 015 DDL 后中断恢复。
- Java 真实 MySQL 验证只允许 v1.1 新建、legacy v1.0 可读、incident projection 漂移 fail-closed。

## 限制

- 本 Change 只建立可执行目标的 provenance root，不执行 Batch/Line 动作。
- Java 仅保存 incident；下一 Change 必须通过 Java 业务事实解析 Batch/Line，禁止接受调用者自由目标。
