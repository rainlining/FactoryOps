# Learning Plan：2026-08-15-start-agent-run-from-inbox

## 元数据

- `learning_level`: `deep`
- `status`: `passed`

## 学习目标

1. 沿 Kafka record → Inbox → Run → offset commit 真实调用链定位代码。
2. 解释为什么两个事务仍可通过 at-least-once 与幂等可靠恢复。
3. 判断三个崩溃窗口中的数据库与 offset 状态。
4. 区分 retryable adapter failure 与 fatal integrity failure。

## Owner 修改任务

在 Review 会话中增加一个可观察字段或精确失败分类，并同步修改真实调用链测试；任务必须要求理解 offset 完成不变量，而不是机械改名。

## Failure/Debug Exercise

- 注入：Inbox commit 后、Run 创建前失败一次。
- 预期：Inbox=1、Run=0、offset 未提交。
- 恢复：关闭故障后重投同一 record。
- 证据：Inbox 仍为 1、Run 变为 1、initial history 为 1、offset 最终提交。
- 回答：为什么 duplicate-identical Inbox 仍必须调用 Starter。

## Learning Gate

- [x] 解释真实设计与取舍。
- [x] 完成端到端调用链 Walkthrough。
- [x] 定位 retryable 与 fatal 失败路径。
- [x] 完成 Owner 修改任务。
- [x] 完成 Failure/Debug Exercise。
- [x] 指出 offset、Inbox 幂等和 Run 幂等实际执行位置。
- [x] Review 最终 diff 并明确接受。

## 完成记录

2026-08-15，项目所有者确认本 Change 的 Learning Gate 已在独立 Review/Learning 会话完成，并明确要求执行最终 Diff Review 和归档。最终实现独立复审结论为 READY：0 Critical、0 Important、0 Minor。
