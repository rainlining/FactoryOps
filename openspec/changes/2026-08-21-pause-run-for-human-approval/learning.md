# Learning

- `learning_level`: `deep`
- Owner Review/Learning Gate 延后至 demo milestone，当前不得 completed/archive/main merge。

## Walkthrough 目标

沿 `HumanApprovalService.save` 定位 provenance 锁、Run 锁、Approval current/history、Run CAS 与 transition history，说明为什么不能调用会另开事务的公共 lifecycle service。

## Owner 小修改

在 Learning Gate 将固定 actor ID 改为 Owner 选择的新值，并更新对应断言，验证 transition provenance 的语义而非机械改名。

## Failure/Debug Exercise

注入 Run transition insert CHECK failure：预期 Approval current/history 与 Run update 全回滚；观察三类表行数/状态；清理临时 CHECK 后重放成功。Owner 应能解释为什么单独重试 Run update 会破坏原子性。
