# Verification

- `status`: `technically-verified-with-environment-limit`
- `verified_at`: `2026-08-22`

## 通过

- `python -m unittest discover -s frontend -p 'test_*.py' -v`：8 passed。覆盖事件顺序、HTTP transport、批次唯一结论、真实 Specialist 并行编排、取消保留证据、新旧历史删除与 DOM contract。
- `node --check frontend/dashboard.js`：exit 0。
- `python -m py_compile frontend/demo_server.py`：exit 0。
- `python -m ruff check frontend`：All checks passed。
- `python -m ruff format --check frontend`：3 files already formatted。
- `python -m pytest -q`（contracts）：154 passed。
- 真实 HTTP：`dashboard.html` 返回 200；创建 `http-smoke` Run 后 `/api/runs/{id}` 返回 RUNNING，`/events?after=0` 返回真实 `VISION 1/2` 事件。
- 浏览器：中文批次作战室正常渲染；7 个节点（Vision、3 Specialist、Coordinator、Risk、Approval）；控制台 0 error；旧 10 产品历史只读展示批次结论且明确“仅查看，不调用模型”。
- `git diff --check`：通过。
- `git status --short` 未出现 `dataset/` 修改。

## 受环境阻塞

- Agent Service 全量：93 passed、6 failed、163 errors；失败集中为 Docker Desktop Linux named pipe 不存在，MySQL/Kafka Testcontainers 无法启动，不是本 Change 断言失败。
- Java `mvn verify -q`：10 个 integration test errors，原因同为 Docker environment unavailable；单元测试日志中的预期故障注入不代表失败。
- 仓库全量 Ruff 存在大量既有历史告警；本 Change 涉及的 `frontend/` 独立 Ruff check/format 已通过。

## 独立审查

独立子 Agent 报告 0 Critical、4 Important。已修复：Agent 输出 HTML escaping；新版 Run/事件事务删除；取消/失败保留已完成证据并支持新 Run 重试事件；Specialist 改为真实并行并增加事件序列锁、Approval 节点、节点耗时和输出摘要。

## 限制

本地 HTTP Run 没有真实 Kafka provenance，页面明确显示“本次本地运行未经过 Kafka”。没有伪造 topic、partition 或 offset。Docker 恢复后仍需补跑 Agent Service 和 Java 全量集成验证。
