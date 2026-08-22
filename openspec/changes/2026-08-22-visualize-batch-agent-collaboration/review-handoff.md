# Review Handoff

- `status`: `review-handoff-ready`
- `change_id`: `2026-08-22-visualize-batch-agent-collaboration`
- `learning_level`: `delegated`
- `branch`: `codex/executive-demo-packaging`
- `worktree`: `.worktrees/executive-demo-packaging`
- `base_commit`: `a566929`
- `implementation_head`: `6b58997edec0c0521ac138f1f316f6d8923e0f17`

## 已实现

- SQLite 持久化 Run job 与单调 progress event。
- `/api/runs` 后台运行、Run 查询、增量事件查询、取消和失败重试入口语义。
- Vision 逐产品，Quality/Production/SLA 每产品真实并行，Coordinator/Risk 每批次唯一结论。
- 取消与失败保留已完成产品证据；历史查看不调用模型。
- 批次作战室、真实进度、Agent 拓扑、审批节点、耗时、输入/输出摘要、证据与事件详情。
- Kafka/HTTP transport 诚实展示。

## 调用链

`dashboard.js::runBatch` → `POST /api/runs` → `create_run` → background `process_batch_run` → `append_progress_event` → `GET /api/runs/{id}/events` → `renderProgress/renderTopology` → `complete_run` → `showResult`。

失败/取消：Provider exception 或 `/cancel` → FAILED/CANCELLED progress event → partial result 保存 → 历史可审计。重试由保留的当前批次创建新 Run，并写入 RETRYING 事件，不改写原 Run。

## 独立审查

审查发现 0 Critical、4 Important，均已修复：DOM XSS、新历史删除、部分证据丢失、伪并行/缺审批与耗时。建议复核 `frontend/test_demo_server.py` 的取消和删除测试，以及 `dashboard.js` 的 HTML escaping 和只读历史路径。

## 验证与限制

详见 `verification.md`。Frontend 8 tests、Contracts 154 tests、Ruff、Node、Python compile、HTTP 和浏览器验证通过。Docker Desktop 不可用导致 Agent MySQL/Kafka 与 Java Testcontainers 全量回归无法完成，已明确记录，不伪造通过。

## 非目标

未重写 Java 状态机或 Kafka Runtime；本地 HTTP Run 不展示虚假 Kafka provenance；未修改 `dataset/`。

## 建议阅读顺序

1. `design.md`
2. `frontend/test_demo_server.py`
3. `frontend/demo_server.py::process_batch_run`
4. `frontend/dashboard.html`
5. `frontend/dashboard.js::renderProgress/renderTopology/showStoredRun`
6. `verification.md`

禁止其他会话并发修改此 worktree，直至 review 完成。
