# Review Handoff：<change-id>

## 交接元数据

- `change_id`: `<change-id>`
- `learning_level`: `deep | standard | delegated`
- `feature_branch`: `<branch>`
- `worktree`: `<absolute path>`
- `base_commit`: `<sha>`
- `head_commit`: `<sha>`
- `implementation_status`: `review-handoff-ready`
- `review_session`: `pending | <task/thread reference>`

## 已实现范围与非目标

- 已实现：
- 明确非目标：

## 关键设计决定与不变量

- 决定：
- 不变量：

## 真实文件与调用链

1. 入口：
2. 编排：
3. 核心规则：
4. 持久化、Event、Agent 或 Tool 边界：
5. 失败与恢复：
6. 对应测试：

## 验证证据

```text
Command:
Actual:
Result:
```

## 已知限制与剩余风险

- 限制：
- 风险：

## Review/Learning 任务

- 建议阅读顺序：
- 项目所有者亲自修改：
- Failure/Debug Exercise：
- Learning Gate 仍需确认：

## 恢复与并发保护

- 进入 worktree 后先运行：`git status --short`。
- 确认当前 branch 和 head commit 与本文件一致。
- Review 会话开始后，实现会话不得继续修改该 Change 或 worktree。
- Deep Change 在 Learning Gate 通过前不得归档或合并 `main`。
