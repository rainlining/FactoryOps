# Review Handoff：从工作台处理批次审批

- `status`: `review-handoff-ready`
- `learning_level`: `standard`
- `branch`: `codex/operate-batch-approval-from-workbench`
- `worktree`: `C:\Users\小霖\Desktop\work\project2\FactoryOps\.worktrees\operate-batch-approval`
- `base_commit`: `31ae8d7d3343c5590d64788a180204ef2adccac6`

## 已实现

待审批区、Risk/Coordinator 证据详情、批准/驳回/复检/升级、审批人和意见、二次确认、SQLite 当前态与 append-only history、命令幂等和终态冲突拒绝。复检在同一事务创建新队列 revision；批准只进入待业务执行，不伪造 PLC/MES 结果。

## 调用链

`refreshApprovals → GET /api/batch-approvals → list_batch_approvals/_ensure_pending_approval → showApproval → POST /api/batch-approvals/{item}/decision → decide_batch_approval → batch_approvals + batch_approval_history + batch_queue_items`。

## 验证与限制

前端 25 passed、Contract 154 passed、Ruff/format/node/py_compile/diff-check 通过；浏览器实际读取现有 5 个待审批批次并展开证据。未替用户作出审批。Java Business API 执行、真实 PLC/MES 和 Kafka 不在本 Change 内。

## 建议 Review 路线

先读 `design.md`，再读 `frontend/demo_server.py` 的审批函数和对应四项测试，最后从 `dashboard.html` 的 `approvalPanel` 沿 `dashboard.js` 的 `refreshApprovals/showApproval/submitApproval` 检查交互。
