# Change 学习计划：2026-08-11-accept-vision-inspection-result

## 元数据
- `learning_level`: `deep`
- `pattern_stage`: `first-deep`
- `first_deep_reference`: `N/A`
- `gate_status`: `passed`

## Review/Learning 目标
- 沿 Controller→Validator→Domain→Application→Transaction→Repository→MySQL 定位代码。
- 解释 Domain invariant 与 Schema/DB constraint 的不同职责。
- 解释为什么预查询不提供并发安全、唯一约束才是最终防线。
- 解释失败事务为何必须退出后再查询。
- 亲自完成一个小型查询/错误映射修改并通过测试。

## Owner 修改任务
由 Review 会话从真实实现中选择一个不承担关键安全兜底的小修改；优先候选：在成功响应增加并验证 `disposition` 枚举映射，或新增按 inspection ID 读取 repository 的只读测试。

## Failure/Debug Exercise
临时把 DuplicateKeyException 恢复查询放回失败事务，或临时移除 DB unique constraint，运行并发测试，观察 rollback-only/重复行/未处理异常；恢复后全套测试必须通过。

## Learning Gate
- [x] 能解释真实设计和事务取舍。
- [x] 能沿成功调用链定位核心代码。
- [x] 能定位并解释并发失败路径。
- [x] 已完成 owner 修改。
- [x] 已完成故障实验并恢复。
- [x] 已 review 最终 diff。

2026-08-12：项目所有者确认已在独立 Review/Learning 会话完成真实调用链 Walkthrough、owner 修改、failure/debug exercise、最终 diff 接受和 Learning Gate。
