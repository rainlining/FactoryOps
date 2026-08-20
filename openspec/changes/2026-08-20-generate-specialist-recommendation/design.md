# 设计：Specialist Recommendation 生成编排

入口 `SpecialistRecommendationGenerationService.generate(command, provider)` 只以 `execution_id` 和调用方稳定提供的 `generated_at` 定位一次生成。服务读取并验证 Execution 与 Task：角色必须是 quality/production/sla，二者均 RUNNING、互相绑定、同 Run、同 role、同 context snapshot，且 Execution 必须是 Task current execution。

若该 execution 的 recommendation key 已存在，服务在调用 provider 前直接返回 existing identical 结果，避免 replay 重复产生模型成本。首次生成时构造 `SpecialistGenerationContext`，只包含 run/task/execution identity、role、task type、context snapshot ID 和输入 evidence refs；不得包含 Evaluation ground truth。provider 返回 `SpecialistRecommendationDraft`，无权设置 identity、contract version 或 generated_at。

应用层由 execution ID 计算 recommendation key，并由 key 摘要确定性派生 recommendation ID，组合 v1.0 Contract 后调用 `SpecialistRecommendationService.save`。Provider 调用期间不持有数据库连接或事务；保存阶段 persistence 重新锁定 Task/Execution 并校验 current RUNNING ownership，因此调用期间 parent 收口会导致拒绝且不留 Recommendation。

`RecordedSpecialistProvider` 接受启动时显式注入的 role→draft 映射，返回深拷贝，保证演示可复现且调用方不能通过后续修改篡改输出。它不是业务规则或真实 AI，不读取仓库 fixture/dataset，也不自动猜测检测结论。

失败路径：parent 缺失/非当前 RUNNING/上下文错配在调用 provider 前拒绝；provider 异常包装为 generation failure 且不写库；draft 违反 Contract 由 validator 拒绝；并发 identical 由既有 key advisory lock 收敛为一个 APPLIED 和一个 DUPLICATE_IDENTICAL。任何失败均不推进 Execution/Task。

测试覆盖三种 role draft、deterministic identity、调用前 replay、provider exception、非法 draft、非 Specialist/上下文错配、真实并发 identical 和 provider 调用期间 parent 失效。
