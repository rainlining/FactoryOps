# 技术选型

- 采用一次原子 attempt replacement，而不是先失败再异步重新 claim：现有 lease 只 claim PENDING Task，中间态会留下无法接管的 RUNNING Task。
- 保留同一 lease：retry 是当前 owner 的连续动作；跨 worker crash recovery 留给 heartbeat/recovery Change。
- 使用 MySQL named advisory lock 串行化 request key，与已审查的 Start/Completion 模式一致。
- 安全错误码使用小型 allowlist，避免仅凭调用方声明 retryable 就重试未知失败。
- 不引入通用 policy engine；max attempts 是本 Change 唯一预算规则。
