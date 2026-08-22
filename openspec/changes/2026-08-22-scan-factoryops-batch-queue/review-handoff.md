# Review Handoff：扫描 FactoryOps 批次队列

- `status`: `review-handoff-ready`
- `learning_level`: `delegated`
- `branch`: `codex/scan-factoryops-batch-queue`
- `worktree`: `C:\Users\小霖\Desktop\work\project2\FactoryOps\.worktrees\scan-factoryops-batch-queue`
- `base_commit`: `56c0a0de0233b9506f73dc99303a4f09a768f9cf`
- `implementation_head`: `de609d4f1193837ee909128069f834e85deaac2f`

## 已实现

一次选择根目录后，直接子目录形成独立持久化批次；SHA-256 清单支持幂等和 revision；默认单并发连续派发独立 Run。严格 Risk JSON 由确定性路由器映射到 `QA_ACCEPTED`、`RECHECK_REQUIRED`、`WAITING_FOR_APPROVAL` 或 `FAILED`。支持暂停、取消、重试、跨 root 隔离和重启恢复。

## 调用链

`groupBatchFiles/buildBatchManifest` → `POST /api/batch-queues/scan` → `scan_batch_queue` → `start_queue/_run_queue` → `create_run/process_batch_run` → `parse_risk_decision/route_batch_outcome` → `renderQueue`。启动时 `recover_batch_queue` 收口失去线程的 Run，并在原队列为 RUNNING 时继续剩余批次。

## 审查与验证

独立审查累计报告 0 Critical、5 Important，均已用回归测试修复。局部 17 passed、Contract 154 passed、Ruff/format/node/py_compile/diff-check 通过；浏览器已验证两批队列展示。Docker 不可用导致 Agent/Java 集成测试无法启动，详见 `verification.md`。

未自动消耗用户真实模型 Token；连续调度由受控 Agent fixture 验证。用户点击开始后使用 `.env.local` 的真实 provider。未修改 `dataset/`，未伪称经过 Kafka。

本次恢复修复将运行态统一到仓库根目录 `.factoryops-local/`，避免切换 worktree 后丢失 API 配置与历史。旧历史已迁移，页面实际恢复 3 条已完成运行；1 条遗留 `RUNNING` 记录保留在数据库但不作为完成回放展示。队列图片改为 Artifact 引用，避免 SQLite 保存 base64。按钮现在提供开始、取消、重试及失败原因反馈，终态停止轮询。密钥文件和运行数据库均未纳入 Git。

## Review 恢复

```powershell
git -C "C:\Users\小霖\Desktop\work\project2\FactoryOps\.worktrees\scan-factoryops-batch-queue" status
python -m unittest discover -s frontend -p 'test_*.py' -v
```

后续审批交互必须建立独立 stacked Change；本 Change 不执行 HOLD、STOP_LINE 或业务 RELEASE。
