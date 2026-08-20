# Change 提案：定义 Human Approval Contract

- `change_id`: `2026-08-20-define-human-approval-contract`
- `status`: `review-handoff-ready`
- `learning_level`: `deep`
- `depends_on`: `2026-08-20-evaluate-fusion-risk-decision`
- `feature_branch`: `codex/define-human-approval-contract`

Risk Gate 已能产生 `REQUIRE_APPROVAL`，但系统还不能结构化表达审批请求、人工决定或过期事实。本 Change 冻结 Human Approval v1：绑定唯一 Risk Decision/Fusion，定义 PENDING 到 APPROVED/REJECTED/EXPIRED 的单向 revision，以及确定性 key、canonical 和 relation。

非目标：不写数据库、不提供 API/UI、不改变 Run/Execution、不执行 Java Business Action、不发送 Kafka、不实现权限目录或通知，也不修改 `dataset/`。

学习等级为 `deep`：首次冻结人工权限主体、审批状态机和“审批事实不等于业务动作已执行”的安全边界；Owner Review/Learning 延后至 demo milestone。

## Demo 硬上限路线

从本 Change 起最多 10 个 Change 完成个人演示闭环：1 Approval Contract；2 Approval Persistence；3 Approval Application/API；4 Business Action Contract/API；5 Agent workflow orchestration；6 checkpoint/recovery；7 demo query API；8 demo dashboard；9 dataset-backed recorded scenario；10 end-to-end packaging/observability。允许合并后续相邻小项，但不得新增横向平台能力。
