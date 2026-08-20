# Change 提案：评估 Fusion Risk Decision

- `change_id`: `2026-08-20-evaluate-fusion-risk-decision`
- `status`: `technically-verified`
- `learning_level`: `deep`
- `depends_on`: `2026-08-20-persist-risk-decision-fusion-subject`
- `feature_branch`: `codex/evaluate-fusion-risk-decision`

Coordinator Fusion 与 Risk Decision 已可持久化，但系统尚无运行时 Risk/Policy Gate 将候选动作转换为确定性的允许、阻断或待审批结论。本 Change 新增 Fusion 风险评估应用服务：读取并验证不可变 Fusion，按版本化 v1 策略生成 v1.1 Risk Decision，并通过既有 persistence 幂等保存。

业务规则采用项目总纲已给出的动作风险等级：PASS/RECHECK 为 LOW，REJECT_ITEM/HOLD_BATCH 为 MEDIUM，STOP_LINE 为 HIGH。HIGH 必须等待人工审批；MEDIUM 在 Specialist 明确冲突时等待审批，否则允许；LOW 允许。ESCALATE 在总纲中是进入人工审核流程的路由动作而非业务副作用，本 Change 明确选择 LOW/ALLOW，避免“请求人工介入本身还需先审批”的循环门禁。当前动作集合没有确定性 BLOCK 条件，禁止为了填满枚举而虚构阻断规则。

非目标：不调用 LLM，不生成 Fusion，不实现 Human Approval 状态机，不推进 Execution/Task/Run，不调用 Java Business API，不执行业务动作，不修改 Contract、数据库 schema 或 `dataset/`。

学习等级为 `deep`：这是首次实现最终动作前的确定性安全门，新增 policy ownership、风险分类和审批边界；Owner Review/Learning 延后到 demo milestone，但 Change 不归档、不合并 main。
