# Development Governance

## 需求

### Requirement: Change 使用日期前缀命名

每个 Change ID 和目录名必须使用 `YYYY-MM-DD-修改内容` 格式，日期表示 Change 首次建立日期，修改内容使用小写英文 kebab-case。

#### Scenario: 创建新的 Change

- **Given** 一个准备进入 OpenSpec 流程的新能力
- **When** 创建 Change ID 和目录
- **Then** 名称必须以创建当天的 `YYYY-MM-DD` 日期开头
- **And** 日期后必须使用小写英文 kebab-case 描述单一修改内容

#### Scenario: 后续继续修改已有 Change

- **Given** 一个已经建立的 Change
- **When** 在后续日期继续 review 或实施
- **Then** 不得仅因当前日期变化而修改其日期前缀

### Requirement: 主要能力使用 OpenSpec Change

系统开发流程必须要求主要业务能力和核心工程能力先建立独立 OpenSpec Change，再进入实现。

#### Scenario: 请求实现新的核心能力

- **Given** 一个尚无已接受 Change 的核心能力
- **When** Codex 准备编写实现代码
- **Then** 必须先创建并 review 该能力的 proposal、规格、设计和任务
- **And** 不得以大而模糊的 Change 包含多个核心能力

### Requirement: Change 具有明确学习等级

每个 Change 必须声明 `deep`、`standard` 或 `delegated` 中的一个主要学习等级。

#### Scenario: 首次实现核心工程模式

- **Given** 项目首次实现涉及关键业务正确性或可靠性的工程模式
- **When** 确定 Change 学习等级
- **Then** 必须优先将该模式标记为 `deep`

#### Scenario: 重复实现相同模式

- **Given** 某工程模式已经通过首次 Deep Learning Gate
- **And** 新 Change 没有引入新的关键语义、并发模型或失败模式
- **When** 再次使用该模式
- **Then** 可以按 `standard`，后续再按 `delegated` 管理
- **And** proposal 必须引用首次 deep Change 并说明相同点与新增点

#### Scenario: 重复模式引入新风险

- **Given** 一个看似重复的工程模式
- **But** 新 Change 引入新的事务边界、并发模型、所有权模型或失败模式
- **When** 评估学习等级
- **Then** 不得自动降级
- **And** 必须根据新增风险重新标记，必要时恢复为 `deep`

### Requirement: Deep Change 采用连续实现与内部小任务

Deep Change 必须在编码前完成设计讲解。项目所有者一次性接受范围与设计后，Codex 可以在同一实现会话按可独立验证的内部小任务连续实施，无需逐任务等待项目所有者批准。

#### Scenario: Deep Change 准备编码

- **Given** Change 的学习等级为 `deep`
- **When** 准备编写第一行实现代码
- **Then** Codex 必须先解释设计、数据流、状态或事务、不变量、失败路径和测试策略
- **And** 项目所有者必须先 review 设计

#### Scenario: 已接受设计后连续实现

- **Given** 项目所有者已经接受 Deep Change 的范围与设计
- **When** Codex 开始 apply
- **Then** Codex 可以连续完成 `tasks.md` 中全部内部实现任务
- **And** 不得把每个内部任务变成项目所有者 review 停顿点
- **And** 每个关键语义或事务边界仍必须具有清晰 commit 和验证证据

#### Scenario: Apply 将产生过大核心 diff

- **Given** 一个 apply 同时改变多个关键不变量或多个系统 Contract
- **When** Codex 规划实现任务
- **Then** 必须拆分内部任务、commit 或拆分 Change

### Requirement: 实现与学习通过 Review Handoff 分离

实现会话必须负责把 Change 连续推进到技术验证完成，并生成可由独立 Review/Learning 会话接手的 `review-handoff.md`。Deep Change 在 Learning Gate 通过前不得归档或合并 `main`。

#### Scenario: 实现会话完成技术验证

- **Given** Change 范围内实现和测试已经完成
- **When** 实现会话准备结束
- **Then** 必须把状态更新为 `technically-verified` 和 `review-handoff-ready`
- **And** 必须推送 feature branch
- **And** `review-handoff.md` 必须记录 branch、worktree、base/head commit、真实调用链、验证证据、所有者修改任务和故障实验
- **And** 实现会话不得代替项目所有者完成 Deep Learning Gate

#### Scenario: 独立 Review/Learning 会话接手

- **Given** 一个状态为 `review-handoff-ready` 的 Change
- **When** Review/Learning 会话开始
- **Then** 必须先核对 branch、worktree 和 head commit
- **And** 必须沿 handoff 中的真实文件完成 Walkthrough、所有者修改、故障实验和最终 diff review
- **And** 实现会话与 Review 会话不得同时修改同一 Change 或 worktree

#### Scenario: 技术通过但学习门禁未通过

- **Given** Deep Change 已 technically verified 并生成 handoff
- **But** Learning Gate 尚未通过
- **When** 判断是否可以集成
- **Then** Change 必须保持 `awaiting-learning-gate`
- **And** 不得归档或合并 `main`

### Requirement: Deep Change 必须包含真实学习活动

Deep Change 的学习验收必须以真实代码理解和调试能力为核心，不得以背诵框架或 API 为主要依据。

#### Scenario: 进入 Learning Gate

- **Given** Deep Change 已通过技术测试
- **When** 进行最终学习验收
- **Then** 项目所有者必须能够解释真实设计
- **And** 能沿真实调用链定位代码
- **And** 能解释至少一条失败路径
- **And** 已亲自完成约定的小修改
- **And** 已完成 failure/debug exercise

#### Scenario: 测试通过但学习活动未完成

- **Given** Deep Change 的自动化测试已经通过
- **But** 所有者修改任务或故障实验尚未完成
- **When** 判断 Change 状态
- **Then** Change 必须保持 `awaiting-learning-gate`
- **And** 不得标记为 `completed`

### Requirement: 每个 Change 保存验证证据

每个 Change 必须保存实际执行的验证、结果、限制和验收状态。

#### Scenario: Codex 声称 Change 已验证

- **Given** Codex 准备声明某项能力已完成或可靠
- **When** 提交完成报告
- **Then** `verification.md` 必须包含实际命令或可复现实验及其实际结果
- **And** 不得预填虚构的通过结果

### Requirement: Vision Contract 先于真实 Vision Service

正式实现 MVTec AD 2 Sheet Metal Vision Service 之前，必须先通过独立 Change 冻结视觉质检结果与业务系统之间的版本化 Contract。

#### Scenario: 早期后端需要视觉结果

- **Given** 真实 Vision Service 尚未实现
- **When** 后端或 Evaluation 需要 Inspection Result
- **Then** 必须使用符合已冻结 Contract 的 fake 或 recorded inspection result
- **And** 不得因此提前实现真实 Vision 推理服务

### Requirement: 面向项目所有者的治理材料使用中文

面向项目所有者的治理、设计讲解、学习材料、Code Walkthrough 和验收说明必须使用中文。

#### Scenario: Codex 生成学习或验收材料

- **Given** 材料需要项目所有者 review
- **When** Codex 创建或更新该材料
- **Then** 主体内容必须使用中文
- **And** 英文标识符或术语首次出现时应提供足够的中文解释

### Requirement: Codex 负责 GitHub 发布

Codex 必须负责本项目经过验证的 Git 初始化、分支、提交、推送及必要的 Pull Request 操作。

#### Scenario: 已接受 Change 准备发布

- **Given** Change 已达到其提交阶段或已经完成验收
- **When** 准备向 `https://github.com/rainlining/FactoryOps.git` 发布
- **Then** Codex 必须先确认提交范围并检查 diff
- **And** 必须运行与 Change 风险相称的验证
- **And** 必须由 Codex 完成提交与推送
- **And** 不得混入不属于该提交范围的修改

### Requirement: 评测图片数据默认不进入无关 Change

`dataset/` 必须被视为评测图片数据边界，只有明确的 Evaluation 或 Vision Change 才能修改或提交其内容。

#### Scenario: 治理或后端 Change 准备提交

- **Given** 当前 Change 没有把评测图片纳入范围
- **When** Codex 检查提交 diff
- **Then** 必须排除 `dataset/` 中的内容
