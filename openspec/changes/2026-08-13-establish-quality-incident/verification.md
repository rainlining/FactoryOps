# Change 验证记录：2026-08-13-establish-quality-incident

- `status`: `technically-verified`
- `verified_at`: `2026-08-13`
- `verified_by`: `Codex`

## 实际验证

- `mvn verify`：通过；Java 单元测试 16 项、MySQL/Testcontainers 集成测试 29 项，共 45 项，0 failure、0 error。
- `python -m unittest discover -s contracts/vision_inspection/tests -v`：17 项通过。
- `git diff --check`：通过。
- V1→V4 实际迁移成功；异常 Result 创建/replay、正常跳过、Incident 查询/404、Batch 状态不变和三对象原子回滚均有真实 MySQL 断言。
- 本 Change Java 文件已用 google-java-format 格式化；超长行扫描未发现压缩的类、方法或 import。
- `dataset/` 未修改或提交。

## 限制

- Incident 只有 OPEN，不含状态迁移、列表、权限、Kafka/Outbox 或自动 HOLD。
- 现有 `inspection_id/result_id` 为 TEXT，MySQL 组合外键使用固定长度 SHA-256 列；Java 同时精确比较原始业务 ID。

## 状态

- 技术验收：`passed`
- Walkthrough、owner 修改、failure exercise、Learning Gate：`pending-review-session`
- Change：`review-handoff-ready`
