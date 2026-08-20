# 技术选型

- 使用同步 Python `Protocol` 作为 provider seam；当前 Agent Service 同步执行，暂不引入异步框架或模型 SDK。
- provider 只返回 draft，不允许控制 identity/provenance，避免模型输出越过确定性边界。
- provider 调用不包在 MySQL 事务内，避免外部延迟占用行锁；保存时重新锁定并 fencing parent。
- Recommendation ID 由 recommendation key 的 SHA 部分前 32 位确定派生，提供 128-bit identity 并保证 retry 稳定。
- recorded provider 只消费显式配置，不读取 dataset/fixture，避免演示数据意外成为生产上下文。
- 本 Change 不自动完成 Worker Execution；Recommendation 是中间事实，完成状态由既有 completion Change 独立处理。
