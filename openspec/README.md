# FactoryOps OpenSpec 工作流

本目录采用 OpenSpec 的 `proposal → specs/design → tasks → apply → archive` 主流程，并增加 FactoryOps 学习项目需要的 `learning.md` 和 `verification.md`。

## 目录结构

```text
openspec/
├── config.yaml
├── README.md
├── specs/                         # 已生效的能力规格
├── changes/
│   ├── _templates/                # FactoryOps Change 模板
│   ├── <active-change>/           # 活跃 Change
│   └── archive/                   # 已完成并归档的 Change
```

单个 Change 的结构：

```text
<change-id>/
├── proposal.md
├── specs/
│   └── <capability>/
│       └── spec.md
├── design.md
├── tasks.md
├── learning.md
└── verification.md
```

## 命名规则

Change ID 和目录名统一使用：

```text
YYYY-MM-DD-修改内容
```

例如：`2026-08-10-establish-openspec-learning-governance`。

- 日期是 Change 首次建立的日期，使用四位年、两位月和两位日。
- 修改内容使用小写英文 kebab-case。
- 名称只描述一个核心能力或工程问题。
- 后续继续修改该 Change 时不更新日期前缀。

## 生命周期

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

Standard 或 Delegated Change 可以把不适用的学习阶段标记为 `N/A`，但不得省略 learning 和 verification 工件。

## 开始一个 Change

1. 按 `YYYY-MM-DD-修改内容` 创建 Change ID，并从 `changes/_templates/` 复制模板到 `changes/<change-id>/`。
2. 先完成 `proposal.md` 和规格增量。
3. 完成 `design.md`；Deep Change 同时完成编码前学习说明。
4. 项目所有者 review 范围和设计。
5. 将 `tasks.md` 拆成可独立验证的 apply 阶段。
6. 分阶段实现，每阶段记录验证证据。
7. 完成真实 Code Walkthrough。
8. Deep Change 进入 `awaiting-learning-gate`，等待所有者修改任务与故障实验。
9. 技术验收和学习门禁都通过后，标记 `completed`。
10. 将规格增量合并到 `openspec/specs/`，随后归档 Change。

## 特殊长期规则

- 重复工程模式采用 `first deep → then standard → then delegated`，但出现新语义、并发模型或失败模式时重新升级。
- 在真实 Vision Service 前先完成 `define-vision-inspection-contract`，早期使用 fake/recorded inspection result。
- Learning Gate 验证理解、定位、修改和调试能力，不考察 API 背诵。
