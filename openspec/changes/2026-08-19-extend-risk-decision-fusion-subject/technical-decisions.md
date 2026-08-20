# 技术选型

- 用 v1.1 而不是修改 v1.0，保持已有 Recommendation consumers 的 schema 和调用兼容。
- `subject_type` 明确区分来源，避免通过字段存在性隐式猜测。
- Fusion binding 复制 run/coordinator execution/round provenance，防止只保存一个 opaque key 后无法审计。
- 不在 Contract 层查询数据库；source fact 存在性和状态由后续持久化/应用层验证。
