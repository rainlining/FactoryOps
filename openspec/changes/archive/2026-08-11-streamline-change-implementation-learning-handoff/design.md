# Change 设计：2026-08-11-streamline-change-implementation-learning-handoff

## 设计目标

把“工程实现”和“代码学习”从频繁交替改为明确交接，在不削弱验证与 Learning Gate 的前提下提升 Change 吞吐量。

## 边界与所有权

- 实现会话拥有 proposal/spec/design/tasks、实现、测试、内部 commits、verification 和 handoff。
- Review/Learning 会话拥有 Walkthrough、owner 修改、故障实验、最终 diff 接受、归档与合并。
- feature branch/worktree 是两个会话之间的真实状态载体，`review-handoff.md` 是交接 Contract。

## 控制流

```text
owner 一次性接受 scope/design
→ implementation session: applying
→ internal tasks + commits + verification
→ technically-verified
→ review-handoff-ready + push
→ implementation session stops
→ review session verifies branch/worktree/head
→ walkthrough + owner task + debug exercise
→ awaiting-learning-gate → completed
→ archive + merge main
```

## 状态与不变量

- 事务边界：`N/A`，纯治理 Change。
- 并发不变量：同一 Change 同时只有一个活跃写入会话。
- 集成不变量：Deep Change 未通过 Learning Gate 不得归档或合并 `main`。
- 可审查不变量：取消 owner 停顿不等于取消内部任务、TDD、commit 或 diff 控制。

## 失败路径

- Handoff 缺少 commit 身份：Review 会话不得开始修改，先补齐。
- 两个会话同时写入：后启动者停止并重新核对 worktree 状态。
- 技术验证通过但 Learning Gate 未通过：保持 feature branch，不合并。
- 实现中发现范围扩张或设计歧义：暂停并请求新决策，不能用连续实现规则静默扩大范围。

## 验证策略

- 检查 AGENTS、OpenSpec README、config、active spec 与模板使用一致生命周期词汇。
- 检查 handoff 模板具有 branch/worktree/base/head、验证、调用链、owner task、failure exercise 和并发保护。
- 检查未修改 `contracts/`、`dataset/` 或业务运行时代码。
- 扫描旧的强制逐 Stage owner review 规则是否仍存在于生效治理文件。

## 方案比较与决定

1. 保持逐 Stage review：学习密度最高，但已证明显著阻塞工程进度。
2. 完全取消学习门禁：速度最快，但违背项目的学习目标。
3. 双会话 Handoff：实现连续、学习集中，保留 Learning Gate。采用此方案。

## 连续 Apply 计划

1. 建立 Change 工件和变更规格。
2. 一次修改生效治理文件与模板。
3. 执行结构、术语、范围和 diff 验证。
4. 推送 feature branch，生成真实 handoff，停止在 review gate。
