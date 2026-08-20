# 技术选型

- 使用同步 Python `Protocol` 作为 provider seam；当前 Agent Service 同步执行，暂不引入异步框架或模型 SDK。
- provider 只返回 draft，不允许控制 identity/provenance，避免模型输出越过确定性边界。
- provider adapter 必须声明并匹配 Execution 冻结的 runtime/prompt/model/tool/context/code 六项 provenance；同 Execution 的 replay shortcut 只有在该绑定与 generated_at 均一致时成立。
- Recommendation evidence 只能是已验证输入 evidence 的子集。当前没有可核验的 Tool/Artifact Store 产物授权接口，因此 recorded provider 的 output artifact 必须为空；后续真实 adapter 需由独立 Change 建立可信 artifact 边界。
- provider 调用不包在 MySQL 事务内，避免外部延迟占用行锁；保存时重新锁定并 fencing parent、context snapshot 与六项 Execution provenance。
- Recommendation ID 由 recommendation key 的 SHA 部分前 32 位确定派生，提供 128-bit identity 并保证 retry 稳定。
- recorded provider 只消费显式配置，不读取 dataset/fixture，避免演示数据意外成为生产上下文。
- 本 Change 不自动完成 Worker Execution；Recommendation 是中间事实，完成状态由既有 completion Change 独立处理。
- Worker Start/Retry/Completion 原来写入 reason code 但 message 为 NULL（Retry 旧 Execution 还沿用 started message），导致完整 Contract reader 无法消费真实运行/历史行；本 Change只补齐既有 reason 的说明文本，不改变状态机或事务语义。
