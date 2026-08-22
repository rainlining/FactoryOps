# Batch Agent Collaboration Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 让用户实时看到一个生产批次的真实处理进度、Agent 协作路径和唯一批次结论，并能零模型调用回看全过程。

**Architecture:** 本地 Python 服务将长任务转为后台 Run，真实调用边界写入 SQLite progress event；浏览器用短轮询读取事件和最终结果。前端以批次作战室替换固定快照首屏，协作拓扑只渲染已发生的状态，Kafka provenance 按 Run 实际入口展示。

**Tech Stack:** Python 3 标准库、SQLite、ThreadingHTTPServer、原生 HTML/CSS/JavaScript、unittest。

**Spec:** `openspec/changes/2026-08-22-visualize-batch-agent-collaboration/design.md`

## Global Constraints

- 不修改 `dataset/`。
- 不伪造进度、Kafka provenance 或 Agent 输出。
- 历史查看不得调用 Agent Provider。
- 本地 HTTP Run 必须明确标记未经过 Kafka。
- 保留 `.env.local`，不提交 API Key。

---

### Task 1: Progress event persistence

**Files:**
- Create: `frontend/test_demo_server.py`
- Modify: `frontend/demo_server.py`

**Interfaces:**
- Produces: `create_run(batch_id, product_count) -> dict`、`append_progress_event(run_id, ...) -> dict`、`get_run(run_id) -> dict`。

- [ ] 写测试：事件 sequence 单调递增、HTTP transport 明确、完成结果可恢复。
- [ ] 运行 `python -m unittest frontend/test_demo_server.py -v`，确认因接口缺失失败。
- [ ] 实现 SQLite `runs`/`progress_events` 最小接口。
- [ ] 重跑测试并提交。

### Task 2: Asynchronous batch orchestration

**Files:**
- Modify: `frontend/test_demo_server.py`
- Modify: `frontend/demo_server.py`

**Interfaces:**
- Produces: `POST /api/runs`、`GET /api/runs/{id}`、`GET /api/runs/{id}/events?after=N`。

- [ ] 写测试：后台 Run 初始立即返回、真实阶段事件、批次级 Coordinator/Risk、失败事件。
- [ ] 观察 RED。
- [ ] 实现后台线程编排与逐调用事件写入。
- [ ] 重跑测试并提交。

### Task 3: Batch command-center UI

**Files:**
- Modify: `frontend/dashboard.html`
- Modify: `frontend/dashboard.css`
- Modify: `frontend/dashboard.js`
- Create: `frontend/test_dashboard_contract.py`

**Interfaces:**
- Consumes: Task 2 Run/event APIs。
- Produces: 进度条、最近活动、Agent topology、批次结论、证据明细、transport 标签。

- [ ] 写 DOM contract 测试，要求新区域和零假快照首屏。
- [ ] 观察 RED。
- [ ] 实现轮询和按事件渲染；只显示已发生状态。
- [ ] 重跑测试、`node --check` 并提交。

### Task 4: Historical collaboration replay

**Files:**
- Modify: `frontend/test_demo_server.py`
- Modify: `frontend/test_dashboard_contract.py`
- Modify: `frontend/dashboard.js`

**Interfaces:**
- Consumes: 保存的 `progress_events` 与 Run payload。
- Produces: `showStoredRun(record)` 零模型回放。

- [ ] 写测试：历史 payload 包含事件；查看按钮不调用运行 API。
- [ ] 观察 RED。
- [ ] 实现历史协作重建、旧记录降级和真实重新运行分离。
- [ ] 重跑测试并提交。

### Task 5: Verification and review handoff

**Files:**
- Modify: `openspec/changes/2026-08-22-visualize-batch-agent-collaboration/{tasks,verification,review-handoff,proposal}.md`

- [ ] 运行 frontend unittest、Python compile、Node syntax 和真实 HTTP/browser 验证。
- [ ] 运行 Agent、Contract、Java、Ruff、diff check 与 dataset 检查。
- [ ] 调用独立子 Agent 审查并修复 Critical/Important。
- [ ] 更新 OpenSpec 证据、提交并推送 review-handoff-ready 分支。
