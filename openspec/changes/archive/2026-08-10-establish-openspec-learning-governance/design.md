# Change 设计：2026-08-10-establish-openspec-learning-governance

## 设计目标

在不创建任何运行时代码和基础设施的前提下，建立一套可在后续 Change 中重复使用、可 review、可留下学习证据的开发治理机制。

## 边界与所有权

- 根目录 `AGENTS.md` 拥有对 Codex 和其他开发 Agent 的仓库级行为约束。
- `openspec/config.yaml` 提供 OpenSpec 项目上下文和各工件生成规则。
- `openspec/README.md` 面向人类说明目录、生命周期和操作顺序。
- `openspec/changes/_templates/` 提供 FactoryOps 扩展模板。
- 当前 Change 的 `specs/development-governance/spec.md` 定义可验证的治理要求。
- 本 Change 不拥有任何业务领域、运行时服务、数据库或消息基础设施。

## 数据流或控制流

后续 Change 按以下控制流推进：

```text
新能力请求
→ 创建 proposal 与规格增量
→ 确定学习等级
→ 完成 design
→ 所有者 design review
→ Deep Change 学习预讲解
→ 分阶段 apply 与验证
→ 真实 Code Walkthrough
→ 所有者修改任务与故障实验
→ Learning Gate
→ completed
→ 合并生效规格并 archive
```

## 状态、事务与不变量

- 状态迁移由 `AGENTS.md` 和 `openspec/README.md` 共同定义。
- 事务边界：`N/A`，本 Change 不包含运行时写入或业务事务。
- 并发与所有权：`N/A`，本 Change 不包含并发执行模型。
- 不变量一：Deep Change 技术测试通过不等于最终完成。
- 不变量二：项目所有者 review 设计前不得进入核心实现。
- 不变量三：模板不得预填虚构验证结果。
- 不变量四：真实 Vision Service 前必须先冻结 Vision Inspection Contract。
- 不变量五：重复模式只有在关键语义和失败模型不变时才允许学习等级递减。

## 失败路径

### Change 过大

- 表现：一个 proposal 同时引入多个核心能力或多个关键 Contract。
- 处理：在 design review 阶段拆分 Change；不得通过扩大 tasks 列表掩盖范围问题。

### 学习流程形式化

- 表现：只生成说明文档或要求背诵 API，没有定位、修改和故障实验。
- 处理：Learning Gate 不通过，状态保持 `awaiting-learning-gate`。

### 验证结果被虚构

- 表现：没有执行命令或实验却在 verification 中填写 PASS。
- 处理：技术验收不通过；改为记录真实命令、实际结果或明确 `not-run`。

### 重复模式错误降级

- 表现：新 Change 引入不同事务或并发语义，却因代码形态相似被标记为 delegated。
- 处理：重新评估学习等级，并在 proposal 记录新增风险。

## 测试与可观测性策略

本 Change 是纯治理 Change，验证重点为：

- 文件结构完整；
- 必需规则可由关键词和人工 review 定位；
- 当前 Change 六类工件齐全；
- 仓库中没有 Java/Python 脚手架、数据库、Kafka 或 Agent Runtime；
- proposal、spec、design、tasks、learning、verification 状态一致。

## 方案比较与决定

### 方案 A：只创建 AGENTS.md

文件少，但无法为每个 Change 保存结构化的规格增量、学习任务和验证证据。

### 方案 B：完全照搬 OpenSpec 默认工件

与官方流程一致，但默认 proposal/specs/design/tasks 无法充分表达 FactoryOps 的亲自修改任务、failure exercise 和 Learning Gate。

### 方案 C：保留 OpenSpec 主流程并增加 learning/verification

本 Change 采用该方案。它保留 OpenSpec 的 proposal、specs、design、tasks 主干，同时把学习与证据作为显式工件，不把它们埋在聊天记录中。

## Apply 分段

1. 建立中文 `AGENTS.md` 和 OpenSpec 项目配置；
2. 建立通用 Change 模板；
3. 建立当前 Change 的完整工件；
4. 执行结构、范围和一致性检查；
5. 停止并等待项目所有者 review，不进入下一 Change。
