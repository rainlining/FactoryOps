# 设计：Coordinator Fusion 生成编排

入口 `CoordinatorFusionGenerationService.generate(command, provider)` 接收 Coordinator Execution ID、round、2～3 个明确的 Recommendation key 与 generated_at。显式 key 集合避免“最新事实”查询在 retry/并发时漂移；缺失角色由输入集合确定。

服务通过完整 Execution reader 与 Recommendation persistence reader 校验 Coordinator Contract、冻结的六项 provenance、来源 Contract/hash/typed columns、同 Run 和唯一角色。相同 fusion key 已存在时，在 provider 调用前比较来源 key 集合与 generated_at，返回 identical/conflicting；历史 replay 不要求 Coordinator 仍 RUNNING。首次生成要求 Coordinator RUNNING。

provider context 只包含 Coordinator/run/round、冻结 provenance 和结构化 Recommendation 摘要/details/evidence，不包含 Evaluation ground truth。provider draft 只能给出候选、冲突、evidence 与 reason；identity、inputs、authorization state 和 generated_at 由应用层控制。draft evidence 必须是来源 Recommendation evidence 的子集。

provider 调用期间不持有事务。保存阶段按既有 Fusion 锁序重新锁定 Coordinator Execution 与排序后的 Recommendation 来源；额外重验调用前六项 Coordinator provenance。parent 状态、provenance 或来源内容漂移时不落 Fusion。并发 identical 由既有 key/ID advisory locks 收敛。
