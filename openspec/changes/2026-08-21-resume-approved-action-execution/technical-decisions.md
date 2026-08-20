# 技术选型

- 使用可重放 saga，不使用 XA/2PC：Java execute 已有 approval-keyed receipt，天然提供跨库幂等恢复锚点。
- 不新增 Agent action receipt 表：Java receipt 是业务副作用事实来源；Agent Run transition 的确定性 request ID 是 workflow 恢复事实。后续需要离线查询时再单独投影，不复制当前事实。
- HTTP adapter 使用标准库而不新增 httpx 依赖：当前只有一个同步内部端点，Protocol 隔离足够；未来统一 Business API client 时可替换 adapter。
- resume transition ID/request ID 从 Approval ID 派生，expected revision 从确定性 wait transition 读取，不从可能已恢复的 current Run 猜测。
- 不直接调用会另开事务的公共 Run lifecycle：本 saga 必须在同一 Agent事务内锁 Run、外调 Java、CAS Run 并写 transition，才能防止审批验证与业务动作之间被并发 cancel/suspend 抢占；状态边与 typed history 仍严格沿用既有 Contract。
- 本 Change 只恢复到 RUNNING：Coordinator success 与 Run success 需要同时冻结 result refs/decision provenance，留给下一个原子收口 Change。
