# Review Handoff：2026-08-11-accept-vision-inspection-result

## 分支定位

- branch：`agent/accept-vision-inspection-result`
- worktree：`.worktrees/accept-vision-inspection-result`
- base commit：`2e939f16bc981b7a81fbf7e7e82cfc21431f9fdd`
- implementation handoff commit：`62429260c6fac1ec130b4ac7cce1d7e630f2c48d`
- owner 修改 commit：`6680e7b`
- 状态：`completed，进入归档合并`

## 已实现调用链

`POST /api/v1/inspection-results`
→ `InspectionResultController.accept`
→ `InspectionResultIntakeService.accept`
→ `VisionInspectionContractValidator.validate`
→ `InspectionResult.decision`
→ READ COMMITTED 预查询
→ INSERT/Flyway 创建的 MySQL 表
→ 唯一键失败时退出写事务
→ 新读事务读取赢家
→ payload hash 比较后返回 replay 或 conflict。

## Review 重点

1. Schema 校验与 Domain 跨字段不变量为何分层。
2. canonical JSON 为什么决定 replay/conflict，而原始 `result_id` 仍需碰撞防御比较。
3. `result_id_hash` 主键与 `inspection_id_hash` 索引如何避免 TEXT 索引收紧 Contract。
4. 为什么捕获 `DuplicateKeyException` 位于失败写事务之外。
5. 并发测试如何证明数据库唯一约束而不是预查询提供最终安全性。

## Learning Gate 结果

- 真实 Code Walkthrough：项目所有者确认完成。
- Owner 修改：成功响应增加 `disposition`，测试覆盖 `CREATED` 与 `REPLAYED`。
- Failure/debug exercise：项目所有者确认完成并恢复。
- 最终 diff 与 Learning Gate：项目所有者于 2026-08-12 明确接受。
