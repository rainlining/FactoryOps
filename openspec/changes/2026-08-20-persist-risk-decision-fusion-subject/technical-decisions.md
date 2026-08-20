# 技术选型

- 在同一 `risk_decisions` 表扩展 subject columns，避免分裂两套 Decision identity/admission 语义。
- `subject_type` 是持久化 discriminator；Recommendation/Fusion FK 使用 RESTRICT。
- 同一 decision key/ID 的 admission lock 逻辑不变；父事实锁按 subject type 选择。
