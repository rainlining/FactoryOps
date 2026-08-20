# 设计：确定性 Fusion Risk Gate

入口 `FusionRiskEvaluationService.evaluate(command)` 接收 fusion key 与调用方稳定提供的 `generated_at`。服务先通过 `CoordinatorFusionService.get_by_key` 读取并完整校验 Fusion provenance，再由纯函数 `evaluate_fusion_policy` 依据 `fusion.proposed_action` 和 `has_conflict` 计算 gate，构造 v1.1 Risk Decision，最后交给 `RiskDecisionService.save`。Risk persistence 会在自己的事务内重新锁定并验证 Fusion，因此读取与保存之间即使发生数据库损坏也不会把未验证结论落库。

Decision key 继续使用冻结的 `compute_decision_key(fusion_key)`；Decision ID 确定性取该 key SHA 部分的前 32 位并加 `RSK-`，使相同 Fusion 的并发评估共享 key/ID admission。`generated_at` 属于事实内容，由 command 显式携带；同一命令重试为 identical，不同时间或策略结果重用同一 Fusion 则为 conflicting，不改写历史。

策略表：

| 动作 | 风险 | 无冲突 | 有冲突 |
|---|---|---|---|
| PASS / RECHECK | LOW | ALLOW | ALLOW |
| REJECT_ITEM / HOLD_BATCH | MEDIUM | ALLOW | REQUIRE_APPROVAL |
| STOP_LINE / ESCALATE | HIGH | REQUIRE_APPROVAL | REQUIRE_APPROVAL |

`ALLOW` 的 `allowed_actions` 只包含 proposed action；`REQUIRE_APPROVAL` 为空，明确表示审批前没有动作获得授权，且本 Change 不替审批系统选择 fallback。Policy refs 固定版本化为 `policy:risk-action-v1`，冲突升级另记录 `policy:risk-conflict-v1`。reason codes 由规则分支确定；confidence 继承 Fusion rank 1 candidate score，而不是声称新的模型置信度。

失败路径：Fusion 不存在或完整性损坏时拒绝且不写 Decision；rank 1 与 proposed action 的关系已由 Fusion Contract 保证，但纯 policy 仍拒绝无法匹配的候选；Risk persistence 的 identical/conflicting 分类原样透传。服务不推进任何生命周期，因此不引入跨表状态事务。

测试使用真实 MySQL 覆盖 LOW、MEDIUM conflict、HIGH、identical replay、concurrent identical、missing/corrupt Fusion 和无生命周期副作用；纯函数覆盖完整动作矩阵。
