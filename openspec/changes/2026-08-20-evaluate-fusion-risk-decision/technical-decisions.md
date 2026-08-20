# 技术选型

- 使用 Python 纯函数实现版本化确定性 policy；本 Change 不引入规则引擎，避免在只有六个动作与两维输入时增加新基础设施。
- 以显式 command timestamp 保证调用重试内容稳定；不在 service 内读取系统时钟。
- 复用现有 Fusion 完整性读取和 Risk persistence 的事务/advisory locks，不复制 SQL 或扩大事务范围。
- HIGH 与 MEDIUM-conflict 只产出 REQUIRE_APPROVAL，不伪装成人工审批已完成；Approval 是后续独立 Change。
- 当前没有足够产品规则定义 BLOCK，保持枚举能力但不生成该分支。
