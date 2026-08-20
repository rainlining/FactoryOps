# 设计：Specialist Recommendation 生成编排

入口 `SpecialistRecommendationGenerationService.generate(command, provider)` 以 `execution_id`、合法 `generated_at` 和 provider provenance 定位一次生成。服务复用完整 lifecycle reader 解码并验证 Execution 与 Task：角色必须是 quality/production/sla，二者均 RUNNING、互相绑定、同 Run、同 role、同 context snapshot，且 Execution 必须是 Task current execution。为使 Worker Start/Retry 产生的行符合既有 Contract，本 Change 同步补齐其非空 lifecycle reason message。

provider 必须声明六项版本 provenance，并与 Execution 冻结值完全一致；校验在 replay shortcut 之前执行。若该 execution 的 recommendation key 已存在且 generated_at 相同，服务在调用 provider 前直接返回 existing identical，避免 replay 重复产生模型成本；不同 generated_at 分类 conflicting。首次生成时构造 `SpecialistGenerationContext`，只包含 run/task/execution identity、role、task type、context snapshot ID、输入 evidence refs 与已校验 provenance，不包含 Evaluation ground truth。provider 返回 `SpecialistRecommendationDraft`，无权设置 identity、contract version 或 generated_at；draft evidence 必须是 context evidence 子集，当前 recorded 边界不接受 output artifact refs。

应用层由 execution ID 计算 recommendation key，并由 key 摘要确定性派生 recommendation ID，组合 v1.0 Contract 后调用 `SpecialistRecommendationService.save`。Provider 调用期间不持有数据库连接或事务；保存阶段 persistence 重新锁定 Task/Execution 并校验 current RUNNING ownership及二者 context snapshot 一致，因此调用期间 parent 收口或 snapshot 漂移都会导致拒绝且不留 Recommendation。

`RecordedSpecialistProvider` 接受启动时显式注入的 role→draft 映射，返回深拷贝，保证演示可复现且调用方不能通过后续修改篡改输出。它不是业务规则或真实 AI，不读取仓库 fixture/dataset，也不自动猜测检测结论。

失败路径：parent 缺失/非当前 RUNNING/上下文错配在调用 provider 前拒绝；provider 异常包装为 generation failure 且不写库；draft 违反 Contract 由 validator 拒绝；并发 identical 由既有 key advisory lock 收敛为一个 APPLIED 和一个 DUPLICATE_IDENTICAL。任何失败均不推进 Execution/Task。

测试覆盖 recorded role draft、deterministic identity、调用前 replay、provider provenance/evidence/artifact 越界、provider exception、非法 draft、上下文错配、barrier 强制的真实并发 identical，以及 provider 调用期间 parent 收口或 snapshot 漂移。
