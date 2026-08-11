# FactoryOps 开发治理

## 1. 沟通语言与项目定位

- 面向项目所有者的设计说明、学习材料、Code Walkthrough 和验收说明必须使用中文。
- 代码标识符、协议字段和业内通用技术名词可以使用英文，但首次出现时应给出中文解释。
- FactoryOps 同时是工程项目和学习项目。交付代码不是唯一目标；项目所有者能够理解、定位、修改和调试关键实现同样属于交付目标。
- 项目发布到 `https://github.com/rainlining/FactoryOps.git`。
- 项目所有者已长期授权 Codex 负责本项目的 Git 初始化、分支、提交、推送及必要的 Pull Request 操作；项目所有者不需要手动完成 GitHub 提交。
- 每次提交前，Codex 必须确认 Change 范围、检查 diff，并运行与风险相称的验证；不得提交无关修改或虚构验证结果。
- 一个已接受的 OpenSpec Change 原则上形成边界清晰的提交；若 Deep Change 需要多个阶段提交，提交边界必须与 `tasks.md` 的 apply 阶段对应。
- `dataset/` 保存评测图片数据；除非当前 Evaluation 或 Vision Change 明确纳入范围，不得修改或混入无关提交。

## 2. 事实来源与范围

- `FactoryOps_Project_Spec_v0.2_MultiAgent_Architecture.md` 是项目顶层产品与架构规格。
- `openspec/specs/` 保存已经生效的能力规格。
- `openspec/changes/<change-id>/` 保存尚在开发或等待验收的 Change 工件。
- 主要能力必须优先通过 OpenSpec Change 开发。
- 当顶层规格存在歧义时，必须在当前 Change 中记录选择、理由和非目标，不得静默猜测。
- 不得借当前 Change 实现无关能力或进行无关重构。

## 3. Change 范围

- Change ID 和目录名必须使用 `YYYY-MM-DD-修改内容` 格式，例如 `2026-08-10-establish-openspec-learning-governance`。
- 日期使用创建 Change 当天的公历日期，固定为四位年、两位月、两位日；修改内容使用小写英文 kebab-case，简洁描述单一核心能力。
- Change 创建后不得仅因实施日期变化而修改日期前缀；日期表示 Change 首次建立日期，不表示最后修改日期。
- 一个 Change 原则上只解决一个核心业务能力或一个核心工程问题。
- 禁止创建 `implement-backend`、`implement-multi-agent-system`、`implement-reliability` 等过大 Change。
- 工程初始化、配置和脚手架只能在当前能力确实需要时引入。
- 如果一个核心 diff 无法在一次专注 review 中解释清楚，必须拆分 Change 或拆分 apply 阶段。
- 同一次核心 apply 不应同时发明数据库模型、API Contract、Kafka Contract 和 Agent Contract。

## 4. 学习等级

每个 Change 必须且只能声明一个主要学习等级：

- `deep`：项目所有者必须理解真实设计和核心实现、沿调用链定位代码、亲自完成一个小修改，并完成 failure/debug exercise。
- `standard`：项目所有者需要理解架构边界、关键取舍和真实调用链，并完成常规验证与 diff review。
- `delegated`：Codex 可以主要负责实现，项目所有者负责运行验证和 diff review。

学习等级必须写入 `proposal.md` 和 `learning.md`。

### 4.1 重复工程模式的等级递减

- 重复出现的工程模式遵循 `first deep → then standard → then delegated`。
- 第一次实现核心模式时执行完整 Deep Learning Gate。
- 后续使用相同语义、相同并发模型和相同失败模型时，不重复完整学习流程。
- 如果后续 Change 引入新的关键语义、事务边界、并发模型、所有权模型或失败模式，必须重新评估等级；必要时恢复为 `deep`。
- 等级递减必须在 `proposal.md` 中引用首次 deep Change，并说明“相同点”和“新增点”，不得只因为代码相似就自动降级。

## 5. OpenSpec Change 必需工件

每个 Change 目录至少包含：

- `proposal.md`：动机、范围、非目标、依赖、学习等级。
- `specs/<capability>/spec.md`：可验证的新增或变更需求及场景。
- `design.md`：边界、数据流、状态、失败路径、测试策略和设计取舍。
- `tasks.md`：按可独立验证阶段拆分的任务清单。
- `learning.md`：学习目标、Code Walkthrough 要求、亲自修改任务、故障实验和 Learning Gate。
- `verification.md`：实际执行的验证命令、结果证据、限制和验收状态。

纯治理或文档 Change 可以没有运行时代码测试，但仍必须验证结构、链接、范围和工件一致性。

## 6. Change 生命周期

Change 按以下状态推进：

```text
proposed
→ design-reviewed
→ learning-preflight-passed
→ applying-stage-1 ... applying-stage-N
→ technically-verified
→ walkthrough-completed
→ awaiting-learning-gate
→ completed
→ archived
```

- `proposed`：proposal 和规格增量可供 review。
- `design-reviewed`：项目所有者接受设计与边界。
- `learning-preflight-passed`：Deep Change 的编码前讲解已经完成并被理解。
- `applying-stage-N`：只实施当前已同意的小阶段。
- `technically-verified`：测试和验证通过，但不表示 Deep Change 已完成。
- `walkthrough-completed`：已基于真实文件和符号讲解调用链。
- `awaiting-learning-gate`：等待项目所有者完成亲自修改与故障实验。
- `completed`：技术验收和对应学习门禁均通过。
- `archived`：规格增量已经合并到 `openspec/specs/`，Change 历史被归档。

未经项目所有者 review，不得从设计阶段直接进入实现。Deep Change 未通过 Learning Gate 时不得标记为 `completed`。

## 7. Deep Change 编码前讲解

Deep Change 在编写实现代码前，Codex 必须用中文解释：

1. 要解决的业务问题和工程问题；
2. 组件边界与所有权；
3. 端到端数据流；
4. 状态迁移、事务边界和关键不变量；
5. 并发和所有权假设；
6. 主要失败路径；
7. 适用时的 timeout、retry、idempotency 和 recovery 行为；
8. 测试与可观测性策略；
9. 被放弃的方案及其取舍。

讲解的目标是建立实现所需的心智模型，不要求背诵框架或 API。

## 8. 分阶段 Apply 与 diff 控制

- Deep Change 必须分阶段 apply。
- 每个阶段只能有一个可独立验证的目标。
- 每个阶段应优先从失败测试或可执行规格开始。
- 改变关键不变量、事务边界或并发语义后，应先停下来 review，再继续下一阶段。
- Deep Change 单次核心 apply 建议控制在约 200～400 行生产代码；这是拆分提醒，不是机械验收指标。
- 生成文件、迁移和测试夹具可以单独评估，但仍必须可解释、可验证、可回退。

## 9. FactoryOps 不可破坏的架构边界

- Java 负责确定性业务规则、领域校验、事务、审批、审计和业务副作用。
- Agent 不得直接修改 MySQL 业务表；业务动作必须经过版本化 Java Business API。
- Kafka 连接 Business World 与 Agent World，不作为 Agent 自由聊天传输层。
- Agent 之间必须使用版本化结构化 Contract。
- LLM 输出不得绕过确定性的风险、权限、状态迁移和审批检查。
- Evaluation ground truth 不得进入 Agent Context。
- 在真实 Vision Service 完成前，使用 fake 或 recorded inspection result；视觉边界由独立的 `define-vision-inspection-contract` Change 先行冻结。
- 大型 Artifact 不应在已有 Artifact Store 责任边界时直接写入 MySQL。

## 10. 可靠性规则

- Kafka Consumer 必须假设 at-least-once delivery。
- 产生业务副作用的操作必须支持幂等。
- 数据库状态与事件发布必须使用明确设计的一致性机制，例如 Transactional Outbox。
- Retry 只能用于已经分类为可安全重试的操作。
- 分布式锁必须定义 owner、过期策略和安全释放条件。
- Checkpoint、Resume 和 Replay 必须保留原始 Run 与 Decision Provenance。
- Replay 必须创建可区分的派生 Run，不得改写历史 Run。
- 高风险动作必须经过 Risk/Policy Gate 和相应审批策略。

## 11. 验证要求

每个 Change 必须根据风险定义：

- 局部不变量的单元测试；
- 持久化或传输边界的集成测试；
- API、Event 和 Agent Output 的 Contract Test；
- 至少一个负向或失败路径测试；
- 实际使用的验证命令；
- 可在日志、数据库、事件或 Trace 中检查的证据。

“已修复”“事务安全”“幂等”“可恢复”等结论必须由实际测试或可复现实验支持。

## 12. 真实 Code Walkthrough

Change 技术验证完成后，Codex 必须基于真实文件、类、函数和测试提供中文 Code Walkthrough，至少覆盖：

- 入口；
- 应用层编排；
- 领域校验；
- 事务边界；
- 持久化或事件边界；
- 适用时的 Agent、Model 和 Tool 边界；
- 错误及恢复路径；
- 对应测试。

仅提供概念架构图不算完成 Code Walkthrough。

## 13. 项目所有者亲自修改任务

每个 Deep Change 必须留下一项由项目所有者亲自完成的小修改。该任务必须：

- 修改当前能力的真实组成部分；
- 足够小，不要求重新设计整个 Change；
- 需要理解语义，而不是机械改名；
- 有验收测试或明确预期；
- 不能把缺失的生产关键安全控制留给项目所有者兜底。

Codex 可以解释、给提示和 review，但不得在未获要求时代替项目所有者完成。

## 14. Failure/Debug Exercise

每个 Deep Change 至少包含一个可复现的故障或调试实验，明确写出：

- 注入的故障；
- 预期系统行为；
- 要观察的证据；
- 常见错误行为；
- 清理或复位方法；
- 完成后应能回答的问题。

可选故障包括重复 Kafka 事件、事务冲突、陈旧 Redis Lease、Tool Timeout、非法结构化输出、Agent Crash 或 Checkpoint Resume。

## 15. Learning Gate

Learning Gate 的核心不是背诵框架、注解或 API，而是项目所有者能够：

1. 用自己的话解释真实设计及关键取舍；
2. 沿一次真实成功调用链定位核心代码；
3. 定位并解释至少一条失败路径；
4. 亲自完成约定的小修改；
5. 完成 failure/debug exercise 并依据证据判断行为；
6. 指出事务、幂等、权限或恢复逻辑实际在哪里执行；
7. review 最终 diff 并明确接受 Change。

Deep Change 在上述条件满足前必须保持 `awaiting-learning-gate`，不得标记为最终完成。

## 16. Change 完成报告

每个 Change 的最终报告必须包含：

- 已实现范围和明确非范围；
- 修改的文件与 Contract；
- 验证命令和实际结果；
- 真实 Code Walkthrough；
- 剩余风险；
- 项目所有者修改任务状态；
- failure/debug exercise 状态；
- Learning Gate 状态。
