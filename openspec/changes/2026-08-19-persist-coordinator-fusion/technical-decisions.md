# 技术选型

- 主表保存 typed query columns、canonical JSON 和 SHA-256；关联表保存完整 Recommendation identity/role 集合。
- 多来源按 key 排序加锁，避免不同输入顺序形成锁序反转。
- key 与 ID 双 advisory lock 解决并发 identity split；数据库唯一约束只作最后防线。
- `ON DELETE RESTRICT` 保留 provenance；不使用级联删除。
