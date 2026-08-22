# FactoryOps Batch Queue Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 一次导入 FactoryOps 根目录，将直接子目录持久化为独立批次队列并连续完成真实 Agent 检测与确定性结果路由。

**Architecture:** 浏览器按 `webkitRelativePath` 将文件分批并计算 SHA-256 清单，Python 服务通过 SQLite 保存队列和 revision，后台 dispatcher 默认单并发复用现有 `process_batch_run`。独立 outcome router 从结构化/可判定结果路由到质检通过、待复检、待审批或失败，绝不执行 Java 业务副作用。

**Tech Stack:** Python 3、SQLite、`ThreadingHTTPServer`、原生 JavaScript/HTML/CSS、Python `unittest`。

**Spec:** `openspec/changes/2026-08-22-scan-factoryops-batch-queue/design.md`

## Global Constraints

- 不修改 `dataset/`。
- 每个直接子目录是独立批次；根目录散落文件和二级嵌套目录不进入批次。
- `QA_ACCEPTED` 不得调用 Java Batch release/hold API。
- 待审批只保存候选动作，不执行 `HOLD_BATCH` 或 `STOP_LINE`。
- 本地运行继续标记 `transport.mode=http-local`、`kafka_used=false`。
- 所有生产行为必须先有失败测试，并实际观察 RED。

---

### Task 1: 冻结批次目录清单

**Files:**
- Modify: `frontend/test_dashboard_contract.py`
- Modify: `frontend/dashboard.js`
- Modify: `frontend/dashboard.html`

**Interfaces:**
- Produces: `groupBatchFiles(files) -> {rootName, batches, ignored}`；`buildBatchManifest(batch) -> Promise<{batch_id, display_name, manifest_digest, images}>`。

- [ ] **Step 1: Write the failing contract tests**

断言 HTML 使用根目录选择文案并包含 `queueSummary`、`queueList`；断言脚本定义 `groupBatchFiles`、`crypto.subtle.digest("SHA-256"`，并以相对路径区分直接子目录和嵌套目录。

- [ ] **Step 2: Run RED**

Run: `python -m unittest frontend/test_dashboard_contract.py -v`

Expected: FAIL，缺少队列元素与扫描函数。

- [ ] **Step 3: Implement minimal scanner**

`groupBatchFiles` 只接受形如 `<root>/<batch>/<image>` 的有效图片；`buildBatchManifest` 读取图片字节，计算单图 SHA-256，并按相对路径排序后再计算清单摘要。选择目录后只渲染扫描预览，不启动模型调用。

- [ ] **Step 4: Run GREEN and commit**

Run: `python -m unittest frontend/test_dashboard_contract.py -v`

Commit: `feat(workbench): scan factoryops batch roots`

### Task 2: 持久化队列、revision 与路由事实

**Files:**
- Modify: `frontend/test_demo_server.py`
- Modify: `frontend/demo_server.py`

**Interfaces:**
- Produces: `scan_batch_queue(root_name, batches) -> dict`；`get_batch_queue() -> dict`；`route_batch_outcome(result) -> str`；SQLite 表 `batch_queue_control`、`batch_queue_items`。

- [ ] **Step 1: Write failing repository tests**

覆盖首次扫描创建两批、相同清单幂等、同名清单变化创建新 revision 且旧结果不覆盖、重启恢复、未知/矛盾风险结果返回 `FAILED`。

- [ ] **Step 2: Run RED**

Run: `python -m unittest frontend/test_demo_server.py -v`

Expected: FAIL，`scan_batch_queue` 和 `route_batch_outcome` 尚不存在。

- [ ] **Step 3: Implement SQLite repository and closed router**

队列项至少保存 `item_id/root_name/batch_id/display_name/revision/manifest_digest/images/status/run_id/retry_of/outcome/created_at/updated_at`。扫描事务按 `(root_name,batch_id,manifest_digest)` 幂等；同名新摘要 revision 加一。路由只接受明确的结构化测试字段或受控关键词，无法确定时 `FAILED`。

- [ ] **Step 4: Run GREEN and commit**

Run: `python -m unittest frontend/test_demo_server.py -v`

Commit: `feat(runtime): persist batch detection queue`

### Task 3: 连续派发与恢复

**Files:**
- Modify: `frontend/test_demo_server.py`
- Modify: `frontend/demo_server.py`

**Interfaces:**
- Consumes: `scan_batch_queue`、`create_run`、`process_batch_run`、`route_batch_outcome`。
- Produces: `start_queue(agent_caller=call_agent)`；`pause_queue()`；`dispatch_next(agent_caller)`；`cancel_queue_item(item_id)`；`retry_queue_item(item_id)`。

- [ ] **Step 1: Write failing dispatcher tests**

使用注入的 fake agent 覆盖三批顺序完成、第一批待审批后第二批继续、第二批失败后第三批继续、暂停不派发新批、取消 `QUEUED` 不创建 Run、失败重试产生 `retry_of` 派生 Run。

- [ ] **Step 2: Run RED**

Run: `python -m unittest frontend/test_demo_server.py -v`

Expected: FAIL，dispatcher API 尚不存在。

- [ ] **Step 3: Implement atomic dispatcher**

在 `BEGIN IMMEDIATE` 中将一个 `QUEUED` 项条件更新为 `STARTING`；提交后创建 Run 并绑定，再执行现有批次流程。每次终态路由后继续调度。启动恢复时，关联 Run 已终态则补路由，仍活动则观察，不存在则保存失败原因。

- [ ] **Step 4: Run GREEN and commit**

Run: `python -m unittest frontend/test_demo_server.py -v`

Commit: `feat(runtime): continuously dispatch batch queue`

### Task 4: 队列 HTTP API 与控制台

**Files:**
- Modify: `frontend/test_demo_server.py`
- Modify: `frontend/test_dashboard_contract.py`
- Modify: `frontend/demo_server.py`
- Modify: `frontend/dashboard.html`
- Modify: `frontend/dashboard.css`
- Modify: `frontend/dashboard.js`

**Interfaces:**
- Produces: `POST /api/batch-queues/scan`、`GET /api/batch-queues/current`、`POST /api/batch-queues/current/start|pause`、`POST /api/batch-queue-items/{id}/cancel|retry`。

- [ ] **Step 1: Write failing API/UI tests**

断言路由方法和页面控制项存在；页面必须显示总批次、检测中、质检通过、待复检、待审批、失败，且批次卡片显示图片数、revision、状态和当前 Run。

- [ ] **Step 2: Run RED**

Run: `python -m unittest discover -s frontend -p 'test_*.py' -v`

Expected: FAIL，缺少 API 与队列控制台。

- [ ] **Step 3: Implement APIs and UI state machine**

扫描完成后刷新队列但不自动调用模型；“开始连续检测”启动 dispatcher；“暂停派发”只停止新批；点击运行中批次复用既有进度拓扑，点击终态批次只读显示历史。失败与取消项提供明确重试，等待审批项不提供伪审批按钮。

- [ ] **Step 4: Run GREEN and commit**

Run: `python -m unittest discover -s frontend -p 'test_*.py' -v`

Commit: `feat(workbench): operate batch detection queue`

### Task 5: 真实验证、审查与 handoff

**Files:**
- Modify: `openspec/changes/2026-08-22-scan-factoryops-batch-queue/tasks.md`
- Modify: `openspec/changes/2026-08-22-scan-factoryops-batch-queue/verification.md`
- Modify: `openspec/changes/2026-08-22-scan-factoryops-batch-queue/review-handoff.md`
- Modify: `openspec/changes/2026-08-22-scan-factoryops-batch-queue/proposal.md`

- [ ] **Step 1: Run automated verification**

Run frontend unittest、`node --check frontend/dashboard.js`、`python -m py_compile frontend/demo_server.py`、frontend Ruff check/format、Contract pytest、Agent Service pytest、Java `mvn verify`、`git diff --check` 和 dataset diff 检查；如 Docker 不可用，记录真实失败而不伪造通过。

- [ ] **Step 2: Run browser verification**

启动当前 worktree 服务，选择 `dataset/factoryops`，确认发现 5 个现有批次、队列连续推进、每批独立 Run、一个批次失败不阻塞后续批次、刷新恢复队列、历史查看不调用模型；可用受控 fake/recorded provider 验证调度，不把它标成真实模型输出。

- [ ] **Step 3: Request independent code review**

让子 Agent 检查 Critical/Important：重复派发、清单身份、失败关闭、历史覆盖、XSS、取消/重试、线程和 SQLite 事务。所有 finding 必须经复现测试后修复。

- [ ] **Step 4: Finish artifacts and push**

记录真实结果、限制、base/head、调用链和审查结果，将状态推进到 `review-handoff-ready`，提交并推送 `codex/scan-factoryops-batch-queue`。
