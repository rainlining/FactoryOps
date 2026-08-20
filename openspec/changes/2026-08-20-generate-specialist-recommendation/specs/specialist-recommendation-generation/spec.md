# Specialist Recommendation Generation 规格增量

### Requirement: 生成必须绑定当前 Specialist ownership

服务只能为当前 RUNNING quality/production/sla Execution 生成 Recommendation；Task 与 Execution 必须互相绑定、属于同 Run/role/context snapshot，且 Execution 是 Task current execution。调用 provider 后保存前必须重新 fencing parent；失效时不得落库。

### Requirement: Provider 必须受确定性边界约束

provider 只能接收不含 Evaluation ground truth 的最小上下文并返回 recommendation/details draft；identity、Contract version、generated_at 必须由应用层控制。Provider 异常或非法 draft 不得产生半事实或生命周期副作用。

### Requirement: 生成必须可重放且并发幂等

recommendation key/ID 必须由 execution ID 确定派生。已有可信 Recommendation 时 replay 不得再次调用 provider；首次并发 identical 生成只能保留一个事实，并稳定得到 APPLIED 与 DUPLICATE_IDENTICAL。

### Requirement: Recorded provider 必须明确且可替换

演示 provider 必须只使用显式注入的 role draft、返回隔离副本，不读取 dataset、Evaluation fixture 或数据库业务表；真实模型适配器可在后续通过同一协议替换。
