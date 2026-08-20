# Learning

- `learning_level`: `deep`
- Owner Review/Learning Gate 延后至 demo milestone。

## Walkthrough

沿 terminal Approval save、HTTP execute、receipt validation、wait transition lookup、Run resume 与最终 provenance re-read，解释为什么跨库不能伪装成原子事务。

## Owner 小修改

为 HTTP timeout 配置增加一个合法边界值测试并修改默认值，说明 timeout 与业务 retry policy 的区别。

## Failure/Debug Exercise

让 fake Business client 首次返回 executed 后模拟 Agent resume DB failure；确认 Batch 侧事实视为已执行、Run 仍 WAITING；移除故障后重试得到 Business replay并只写一条 resume transition。
