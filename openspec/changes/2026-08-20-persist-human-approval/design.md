# 设计：Human Approval Persistence

Migration 014 创建 `human_approvals` 当前快照与 `human_approval_history` 不可变 revision。首次保存锁定 approval key/ID admission，再锁定并完整解码 Risk Decision 及其 Fusion provenance，同事务插入 current 与 revision 1 history。终态保存按相同锁序读取 current，Contract relation 必须为 `next-revision`，以 `WHERE revision=1` 更新 current 并插入 revision 2 history。

相同 canonical snapshot 返回 identical；同 key 非法内容或终态竞争返回 conflicting，不覆盖赢家。key/ID split 由两个排序 advisory locks 收敛。读取重验 hash、canonical、typed columns、Risk binding，以及 current 必须等于最高 history revision。外键 RESTRICT 保留 provenance。

不提供通用 update；终态不可再迁移。事务不改变 Risk/Fusion/Execution/Run，也不产生业务动作。
