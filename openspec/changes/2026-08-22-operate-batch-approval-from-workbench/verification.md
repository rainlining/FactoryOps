# Verification：从工作台处理批次审批

- `status`: `technically-verified`

## TDD 证据

- RED：`decide_batch_approval` 缺失导致 2 个服务测试 Error；`approvalPanel` 缺失导致前端 Contract Test Fail。
- GREEN：审批状态机、持久化和 UI 完成后，前端测试 25 passed。

## 实际验证

- `python -m unittest discover -s frontend -p 'test_*.py' -v`：25 passed。
- `python -m pytest -q contracts`：154 passed。
- `python -m ruff check frontend`：All checks passed。
- `python -m ruff format --check frontend`：3 files already formatted。
- `node --check frontend/dashboard.js`：exit 0。
- `python -m py_compile frontend/demo_server.py`：exit 0。
- `git diff --check`：exit 0。
- `git diff --name-only 31ae8d7..HEAD -- dataset`：无输出。

## 浏览器验收

- 共享真实运行数据中识别到 5 个 `WAITING_FOR_APPROVAL` 批次，并显示为“5 项待处理”。
- 实际点击 `batch-003` 审批卡片后，页面显示 `HOLD_BATCH`、`Critical`、10 个产品、四条 policy ref、批次 Coordinator 结论、Risk JSON、审批人/意见和四种操作按钮。
- 未替用户提交真实审批决定；决定事务由测试覆盖，避免改变用户现有的 5 个待审批事实。

## 限制

- `APPROVE` 只记录为 `APPROVED_ACTION_PENDING`；未连接 PLC/MES 时不会宣称已经执行物理动作。
- Java Business API 的真实副作用执行不在本 Change 范围内。
