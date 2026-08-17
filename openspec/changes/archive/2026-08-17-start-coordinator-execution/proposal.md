# Change 提案：启动 Coordinator Execution

## 元数据

- `change_id`: `2026-08-17-start-coordinator-execution`
- `status`: `completed`
- `learning_level`: `deep`
- `depends_on`: `[2026-08-15-start-agent-run-from-inbox, 2026-08-17-persist-agent-execution-lifecycle]`
- `stacked_base_commit`: `8e73eb57a269dc453c78152f84d6a547fd02f633`
- `feature_branch`: `codex/start-coordinator-execution`

## 动机与范围

Inbox 已能创建 PENDING Run，Execution 已能持久化，但尚无原子操作把 Run 绑定到首个 Coordinator attempt。若顺序调用两个现有 Service，崩溃会留下孤立 Execution 或已 RUNNING 却无 Coordinator 的 Run。

本 Change 新增版本化启动命令与 MySQL 单事务编排：创建 Coordinator Execution snapshot/history，同时把 Run 从 PENDING revision 0 推进到 RUNNING revision 1、绑定 Execution 并更新计数；支持请求重放、冲突分类和同 Run 并发单赢家。

## 非目标

- Redis lease、Worker 长期 ownership、心跳、过期接管。
- Task dispatch、专业 Agent、LLM/Tool 调用、自动 retry。
- Context Snapshot 内容存储、Checkpoint/Resume/Replay。
- Java Business API、审批、Evaluation 与 `dataset/`。

## 学习等级

`deep`。虽然复用既有 snapshot/history 和乐观锁，但这是首次在一个事务内维护 Run 与 Execution 两个聚合的一致性，并新增“提交结果不确定时按启动请求恢复”的失败模型，属于新的事务边界。

## 验收

真实 MySQL 证明成功、相同/冲突重放、同 Run 并发、非法 Run 状态和任一 history 失败整体回滚；全仓回归通过并完成独立审查。
