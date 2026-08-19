# 设计

共享 envelope 绑定 Recommendation identity；Risk payload 只表达 policy gate 结果，不表达执行成功。`decision_key = SHA-256("v1\n<recommendation_key>")`。Validator 先做有限数值/高风险动作 preflight，再做严格 Schema、key、唯一数组和 ground-truth 检查；canonical JSON 用排序键和禁止 NaN。

`allowed_actions` 表示当前 Gate 已授权的动作：`ALLOW` 必须包含 proposed action，`BLOCK` 与 `REQUIRE_APPROVAL` 必须排除 proposed action。待审批动作只有后续 Approval 能转化为可执行授权。

Risk Decision 不写数据库、不调用 Approval/Business API。后续持久化 Change 负责父对象 FK，执行 Change 负责 decision 与 approval 的事务边界。
