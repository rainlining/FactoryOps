# Learning

- `learning_level`: `deep`
- 理解 Risk Gate 与 Fusion、Approval、Java Business Action 的边界。
- Walkthrough：`evaluate → Fusion integrity read → pure policy → v1.1 payload → Risk persistence save`。
- Owner 修改任务：在集中 Learning Gate 中新增一个明确的 MEDIUM action reason code，并补对应矩阵测试。
- Failure/debug exercise：损坏 Fusion canonical hash，观察评估拒绝、risk_decisions 无新增；恢复 hash 后用相同 command 成功。
- 当前状态：Owner Review/Learning 延后到 demo milestone。
