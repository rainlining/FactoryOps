# Development Governance 规格增量：连续实现与学习交接

## 变更需求

### Requirement: Change 实现不再要求逐 Stage owner review

项目所有者一次性接受范围与设计后，Codex 必须能够在一个实现会话中按内部小任务连续完成整个 Change，不得把每个任务或 commit 变成 owner review 停顿点。

#### Scenario: 连续实现已接受的 Change

- **Given** 项目所有者已接受 Change 的范围与设计
- **When** Codex 执行 `tasks.md`
- **Then** Codex 可以连续完成全部实现与技术验证
- **And** 仍必须保留可独立验证的小任务、清晰 commit 和失败路径测试
- **And** 只有设计歧义、范围扩张或需要新授权时才暂停询问

### Requirement: 实现会话生成 Review Handoff

实现会话必须在技术验证完成后生成 `review-handoff.md`，推送 feature branch，并停止在 `review-handoff-ready`。

#### Scenario: 向 Review/Learning 会话交接

- **Given** 实现和范围内验证全部完成
- **When** 实现会话结束
- **Then** handoff 必须包含 branch、worktree、base/head commit、范围、真实调用链、验证、风险、所有者修改和故障实验
- **And** Review 会话必须能在不依赖聊天历史的情况下恢复工作

### Requirement: Deep Learning Gate 仍是合并前门禁

分离会话不得降低 Deep Change 的学习验收要求。

#### Scenario: 技术完成但学习未完成

- **Given** Deep Change 已 `review-handoff-ready`
- **But** 项目所有者尚未完成 Learning Gate
- **When** 判断是否归档或合并
- **Then** 必须保持 `awaiting-learning-gate`
- **And** 不得归档或合并 `main`

### Requirement: 同一 Change 具有单一活跃写入者

实现会话和 Review/Learning 会话不得同时修改同一 Change 或 worktree。

#### Scenario: Review 会话接管 worktree

- **Given** handoff 已记录唯一 branch、worktree 和 head commit
- **When** Review 会话开始修改
- **Then** 必须先核对这些身份
- **And** 实现会话必须停止写入
