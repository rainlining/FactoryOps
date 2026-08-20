# 技术选型

- 使用同步 `Protocol` provider seam，与 Specialist Generation 一致；本 Change 提供显式 round→draft 的 recorded provider。
- 生成命令必须显式携带 Recommendation keys，不在数据库中猜测最新 attempt 或最新 role 输出。
- provider provenance 必须匹配 Coordinator Execution 的 runtime/prompt/model/tool/context/code 六项冻结值，并在保存事务内重验。
- Fusion ID 从 fusion key 的摘要确定性派生；authorization 固定 `NOT_EVALUATED`。
- provider evidence 只能引用来源 Recommendation 已有 evidence；Fusion Contract 不含 output artifact，因此不新增 Artifact 边界。
- 不自动完成 Coordinator Execution，Risk Gate 是下游独立能力。
