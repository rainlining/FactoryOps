# Review Handoff

## 恢复信息

- Change：`2026-08-20-generate-coordinator-fusion`
- 学习等级：`standard`（Owner Review/Learning Gate 延后）
- 分支/worktree：`codex/generate-coordinator-fusion` / `C:\Users\小霖\Desktop\work\project2\FactoryOps\.worktrees\generate-coordinator-fusion`
- stacked base：`0f4067d285946152b32e4e67e554e623665d99e7`
- 技术实现 HEAD：`2077514`；最终文档 HEAD 以本文件所在提交为准
- 远端：上游已补推；本分支两次推送均因 GitHub 443 超时失败，待网络恢复后补推并以 `git ls-remote` 核验

## 已实现范围

调用方显式提交 Coordinator Execution、round、2～3 个 Recommendation key 与时间。服务用完整 reader 校验同 Run、唯一角色、Coordinator 状态和六项 provenance；来源按 `role + recommendation_key` 固定排序后交给 provider。provider 只生成 draft，应用层控制 identity、来源、缺失角色、时间与 `NOT_EVALUATED`，persistence 在事务中锁定 Coordinator 与排序来源并保存。

相同历史请求在 provider 前返回 `DUPLICATE_IDENTICAL`；同 Fusion identity 但来源集合或时间不同为 `DUPLICATE_CONFLICTING`。首次生成要求 Coordinator `RUNNING`，历史 replay 不依赖当前运行态。provider 异常、未授权 evidence、畸形 draft、provenance 或来源漂移均不留下 Fusion fact。

非目标：不猜测最新 Recommendation；不执行 Risk、Approval、Business Action；不完成 Run/Execution；不实现真实模型、HTTP/Kafka/Checkpoint/Artifact Store；不改 Contract/schema 或 `dataset/`。

## Walkthrough

1. `CoordinatorFusionGenerationCommand` 与 `CoordinatorFusionGenerationService.generate`。
2. `AgentExecutionLifecycleService.get_execution`、`SpecialistRecommendationService.get_by_key`、`_load_sources`。
3. `FusionGenerationContext`、provider、`RecordedCoordinatorFusionProvider`、`_validate_draft`。
4. `_source_context`、`_source_reference` 与应用层 payload 构造。
5. `CoordinatorFusionService.save` 的 admission、锁与 provenance fencing。
6. `test_coordinator_fusion_generation_mysql.py` 的 replay、并发、重排、畸形 draft、漂移和失败无事实测试。

成功链：command → 完整事实读取 → canonical provider context → draft 校验 → 应用层 payload → persistence locks/fencing → APPLIED。

失败链：非法输入/状态/provenance → `FusionGenerationRejected`；provider 异常 → `FusionGenerationFailed`；外调期间漂移 → `FusionPersistenceRejected` 并回滚；相同并发写 → APPLIED + DUPLICATE_IDENTICAL。

## 审查与剩余状态

独立首审 2 个 Important 已在 `2077514` 修复；同一 Agent 复审为 0 Critical、0 Important，并实跑真实 MySQL 17 passed。完整证据见 `verification.md`。剩余风险是 recorded provider 尚非真实模型适配器，当前只产出 `NOT_EVALUATED`，授权仍由后续 Risk/Approval 链负责。

Owner walkthrough、最终 diff review 与 Learning Gate 延后；本 Change 不归档、不合并 main。禁止其他会话并发修改本 worktree。
