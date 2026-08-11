# Review Handoff：2026-08-11-accept-vision-inspection-result

## 分支定位

- branch：`agent/accept-vision-inspection-result`
- worktree：`.worktrees/accept-vision-inspection-result`
- 状态：`review-handoff-ready`
- 尚未合并、归档或通过 Learning Gate。

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

## Learning Gate 保留项

- 真实 Code Walkthrough：待独立 review 会话完成。
- Owner 修改：待 review 会话确认并由项目所有者完成。
- Failure/debug exercise：待 review 会话执行并恢复。
- 最终 diff 接受：待项目所有者明确确认。

在以上项目完成前，不得标记 `completed`、归档或合并到 main。
