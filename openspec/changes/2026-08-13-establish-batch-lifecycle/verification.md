# Change 验证记录：2026-08-13-establish-batch-lifecycle

- `status`: `technically-verified`
- `verified_at`: `2026-08-13`
- `verified_by`: `Codex`

## 实际验证

- `mvn verify`：通过。Java 单元测试 14 项、MySQL/Testcontainers 集成测试 24 项，共 38 项，0 failure、0 error。
- `python -m unittest discover -s contracts/vision_inspection/tests -v`：通过，17 项。
- `git diff --check`：通过。
- Docker Desktop 29.5.2 与 MySQL 8.4 Testcontainers 实际运行；Flyway V1→V3 全量迁移通过。
- 测试覆盖创建/replay/conflict、状态迁移、异常证据、迁移回填、并发命令、RELEASED 后新 Inspection 拒绝与旧请求 replay。

## 验证说明

- `InspectionMigrationIT` 会有一条预期的 Flyway V2 失败日志，用于验证非法历史数据阻止迁移；测试本身通过。
- 新证据外键形成 Batch→Result→Inspection→Batch 引用环，测试清理器使用连接级 `FOREIGN_KEY_CHECKS=0` 清空隔离数据；生产约束未禁用。
- `dataset/` 未修改、未纳入提交。

## 验收状态

- 技术验收：`passed`
- Code Walkthrough：`pending-review-session`
- 所有者修改：`pending-review-session`
- Failure exercise：`pending-review-session`
- Learning Gate：`pending-review-session`
- Change：`review-handoff-ready`
