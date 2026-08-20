# Coordinator Fusion Generation 规格增量

### Requirement: 生成必须绑定明确且可信的多来源集合

命令必须显式提供 2～3 个唯一 Recommendation key。服务必须完整验证来源事实、同 Run、唯一 Specialist role 与 Coordinator Execution；不得自动猜测最新来源。

### Requirement: provider 必须受最小上下文与 provenance 约束

provider identity 必须匹配 Coordinator Execution 冻结的六项 provenance。provider 只能控制 Fusion draft，不能控制 identity、inputs、authorization 或 generated_at；draft evidence 必须来自源 Recommendation evidence。

### Requirement: replay 与并发必须稳定

Fusion key/ID 必须由 run、Coordinator Execution 和 round 确定派生。相同来源集合与 generated_at 的历史 replay 不得再次调用 provider；不同请求必须 conflicting。首次并发 identical 只能保留一个事实。

### Requirement: 外部调用后的完整 fencing

provider 调用不得持有数据库事务。保存事务必须重新锁定并验证 RUNNING Coordinator、六项 provenance 与全部 Recommendation 来源；任一事实漂移必须拒绝且不留半事实。
