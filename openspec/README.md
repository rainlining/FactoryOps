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
├── review-handoff.md
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
→ applying
→ technically-verified
→ review-handoff-ready
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
5. 将 `tasks.md` 拆成 Codex 内部可独立验证的小任务；它们不是 owner review 停顿点。
6. 实现会话连续完成整个 Change、内部 commits 和技术验证。
7. 生成 `review-handoff.md`、推送 feature branch，并停在 `review-handoff-ready`。
8. 独立 Review/Learning 会话完成真实 Code Walkthrough、所有者修改和故障实验。
9. 技术验收和学习门禁都通过后，标记 `completed`。
10. 将规格增量合并到 `openspec/specs/`，随后归档并合并 `main`。

实现会话与 Review/Learning 会话不得同时修改同一 Change 或 worktree。Deep Change 在 Learning Gate 通过前不得归档或合并 `main`。

## 特殊长期规则

- 重复工程模式采用 `first deep → then standard → then delegated`，但出现新语义、并发模型或失败模式时重新升级。
- 在真实 Vision Service 前先完成 `define-vision-inspection-contract`，早期使用 fake/recorded inspection result。
- Learning Gate 验证理解、定位、修改和调试能力，不考察 API 背诵。
