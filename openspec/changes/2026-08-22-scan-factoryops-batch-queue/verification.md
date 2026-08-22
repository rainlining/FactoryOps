# Verification：扫描 FactoryOps 批次队列

- `status`: `technically-verified`
- `implementation_head`: `de609d4f1193837ee909128069f834e85deaac2f`

## 实际验证

- TDD RED：缺少队列 API/路由/恢复时按预期失败；自由文本错误自动通过和孤儿 Run 恢复测试按预期失败后修复。
- `python -m unittest discover -s frontend -p 'test_*.py' -v`：17 passed。
- `python -m ruff check frontend`：All checks passed。
- `python -m ruff format --check frontend`：3 files already formatted。
- `node --check frontend/dashboard.js`、`python -m py_compile frontend/demo_server.py`、`git diff --check`：exit 0。
- `python -m pytest -q contracts`：154 passed。
- 应用内浏览器实际显示连续队列；API 导入两个受控批次后显示独立 revision、图片数、状态和操作。Smoke 数据随后清理，未调用模型。

## 跨模块限制

- Agent Service：93 passed、6 failed、163 errors；Docker Desktop Linux named pipe 不可用，MySQL/Kafka Testcontainers 无法启动。
- Java `mvn verify -q`：10 个集成 errors，原因同为 Docker/Testcontainers 不可用。
- 本 Change 未修改 Agent Service、Java 或 `dataset/`。

## 独立审查

首轮 0 Critical、4 Important；复审新增 1 个恢复 Important。全部修复：严格 Risk JSON、失败关闭、root 隔离、STARTING 取消、队列 Run 删除保护、重启收口孤儿 Run并继续派发。最终局部验证为 17 passed。

## 2026-08-22 本地状态恢复修复

- 根因：feature worktree 各自读取 `frontend/.env.local` 和 `frontend/demo_runs.sqlite3`，切换 Change 后因此表现为密钥未配置、历史消失；队列图片 base64 同时直接写入 SQLite，造成新库异常膨胀。
- 修复：所有 worktree 统一使用仓库级、Git 本地排除的 `.factoryops-local/`；密钥仍只保存在本机。队列图片落入 `queue-images/` Artifact，SQLite 仅保存摘要和引用，运行时再恢复请求数据。
- 迁移证据：旧库实际包含 2 条同步 Run、2 条异步 Run；页面恢复显示其中 3 条已完成运行，另 1 条 `RUNNING` 不伪装为可回放的完成记录。通用与 Vision API Key 均通过非敏感布尔检查确认已加载，未输出值。
- UI 修复：开始、取消、重试均显示明确结果；后端错误直接呈现；失败行显示失败原因；队列进入终态后停止轮询。
- 新增回归后局部测试：19 passed；Contract：154 passed；Ruff、Node 语法、Python 编译和 diff check 结果见最终提交验证。
