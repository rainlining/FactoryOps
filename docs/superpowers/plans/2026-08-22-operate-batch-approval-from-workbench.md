# Batch Approval Workbench Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 让待审批批次可被理解、决定、持久化和回放。

**Architecture:** 在现有 Python demo server 的共享 SQLite 中增加最小审批状态机和历史表；前端增加单一待审批区。物理业务动作保持失败关闭，仅记录待执行事实。

**Tech Stack:** Python 3、SQLite、原生 JavaScript/HTML/CSS、unittest。

**Spec:** `openspec/changes/2026-08-22-operate-batch-approval-from-workbench/design.md`

## Global Constraints

- 不修改 `dataset/`。
- 不让 LLM 或浏览器直接决定业务状态。
- 不伪称已经执行 PLC/MES 动作。

---

### Task 1: 审批状态机与事务

**Files:** `frontend/test_demo_server.py`, `frontend/demo_server.py`

- [ ] 写入四种决定、幂等、冲突和复检原子性的失败测试。
- [ ] 运行局部测试确认因审批 API 缺失而失败。
- [ ] 实现审批表、列表、详情和决定事务。
- [ ] 运行局部及全量前端测试。

### Task 2: HTTP 与前端交互

**Files:** `frontend/test_dashboard_contract.py`, `frontend/dashboard.html`, `frontend/dashboard.js`, `frontend/dashboard.css`

- [ ] 写入待审批区域、表单和请求路径的失败 Contract Test。
- [ ] 运行测试确认缺少 UI/API 调用而失败。
- [ ] 实现列表、证据详情、四种操作、二次确认和反馈。
- [ ] 运行 Contract、语法与浏览器验收。

### Task 3: 验证与移交

**Files:** 当前 Change 的 `verification.md`, `review-handoff.md`, `tasks.md`

- [ ] 运行前端、Contract、Ruff、格式、编译、diff 和 dataset 检查。
- [ ] 调用独立子 Agent 审查并修复 Critical/Important。
- [ ] 记录证据、提交并推送 feature branch。
