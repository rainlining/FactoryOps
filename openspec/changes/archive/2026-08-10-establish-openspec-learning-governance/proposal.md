# Change 提案：2026-08-10-establish-openspec-learning-governance

## 元数据

- `change_id`: `2026-08-10-establish-openspec-learning-governance`
- `status`: `archived`
- `learning_level`: `standard`
- `first_deep_reference`: `N/A`
- `depends_on`: `[]`
- `spec_refs`: `[development-governance]`

## 为什么要做

FactoryOps 同时承担工程交付与个人学习目标。如果没有仓库级治理，Codex 可能一次生成过大的核心 diff，项目所有者只能理解业务流程而无法理解真实实现，也无法通过失败实验建立后端与 Agent 工程能力。

本 Change 在任何业务实现前建立统一的 OpenSpec 工作流、Change 模板、学习等级、验证证据和 Learning Gate。

## 范围

本 Change 唯一核心能力是建立 FactoryOps 的规格驱动开发与学习治理机制。

包含：

- 中文 `AGENTS.md`；
- `YYYY-MM-DD-修改内容` Change 命名规则；
- OpenSpec 项目配置和目录说明；
- proposal、design、tasks、learning、verification 模板；
- Change 生命周期和状态含义；
- `first deep → then standard → then delegated` 规则；
- Vision Contract 先于真实 Vision Service 的长期规则；
- 基于解释、定位、修改和调试的 Learning Gate；
- 本治理能力的可验证规格。

## 非目标

- 不创建 Java、Python 或前端工程；
- 不创建 FactoryOps 业务代码；
- 不创建数据库 Schema、Kafka Topic 或 Agent Runtime；
- 不安装或运行 OpenSpec CLI；
- 不初始化 Git，不创建 commit，不添加 GitHub remote，不推送远端；
- 不提前创建后续业务 Change 的完整内容。

## 预期影响

- 新增规格：`development-governance`；
- 新增根目录治理文件：`AGENTS.md`；
- 新增 `openspec/` 治理目录和模板；
- 不影响任何运行时 Contract。

## 依赖与顺序

- 前置 Change：无；
- 后续所有主要能力 Change 都依赖本治理机制；
- `define-vision-inspection-contract` 必须排在真实 Vision Service 实现之前。

## 学习等级理由

本 Change 是 `standard`：项目所有者需要理解 Change 工件、状态推进、review 停顿点和 Learning Gate，但本 Change 没有核心业务算法、事务、并发或运行时失败语义，不需要执行完整 Deep Change 学习流程。

## 验收摘要

- 技术验收：目录完整，模板覆盖要求，治理规则相互一致，且仓库中没有业务脚手架或业务代码；
- 学习验收：项目所有者能够说明一个 Change 从 proposed 到 archived 的推进过程，并 review 中文 `AGENTS.md`。

## 归档后治理补充

- 2026-08-11：项目所有者长期授权 Codex 负责本项目后续 Git 初始化、提交、推送及必要的 Pull Request 操作。
- 2026-08-11：项目所有者确认 `dataset/` 是评测图片数据，除明确的 Evaluation/Vision Change 外不纳入修改范围。
- 上述补充已同步到根目录 `AGENTS.md`、`openspec/config.yaml` 和当前有效治理规格。
