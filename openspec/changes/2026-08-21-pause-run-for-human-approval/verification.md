# Verification

状态：`technically-verified`，等待独立子 Agent 审查。

## TDD 与局部验证

- RED：旧实现保存 PENDING Approval 后 Run 仍为 RUNNING、无确定性 wait transition；transition failure 注入不会影响 Approval 保存；读取也不会发现 transition corruption。
- GREEN：`python -m pytest -q services/agent-service/tests/test_human_approval_mysql.py` 为 `18 passed in 21.56s`。
- 真实 MySQL 证据覆盖 applied、identical、并发相同、非 RUNNING、读取期 transition corruption，以及注入 transition CHECK failure 后 Approval current/history 为 0、Run 仍为 `RUNNING/revision 1`。

## 全量验证

- `python -m pytest -q services/agent-service/tests`：`221 passed in 491.42s`。
- `python -m pytest -q contracts`：`154 passed in 2.48s`。
- `mvn verify -q`：退出码 0；全新 worktree 的递归 XML 为 `21 reports / 85 tests / 0 failures / 0 errors / 0 skipped`。
- `python -m ruff check`（本 Change 两个 Python 文件）：通过。
- `python -m ruff format --check`（本 Change两个 Python 文件）：通过。
- `git diff --check` 通过；`git status --short -- dataset` 无输出。

## 限制

本 Change 只暂停 Run；terminal Approval 后的恢复、Java Business API 调用、Coordinator/Run 完成由后续 Change 实现。

## 独立审查

首审：0 Critical、2 Important、1 Minor。Important 为校验错误要求 Run 永久停在 WAITING，以及未把 Run current reason/time 与 transition history 交叉校验；Minor 为并发测试缺精确行数。修复后局部真实 MySQL `18 passed in 22.28s`：新增 WAITING→RUNNING 合法恢复后 Approval 仍可读、Run reason corruption fail closed、从 wait 到 current 的连续合法 transition chain 与 current reason/updated_at 校验，并补 current/history/transition 行数及 revision 断言。等待复审。

修复后全量：Agent `221 passed in 482.01s`；Contract `154 passed in 1.60s`；Java `mvn verify -q` 退出码 0，XML `21 reports / 85 tests / 0 failures / 0 errors / 0 skipped`；Ruff check/format、diff check、dataset check 均通过。
