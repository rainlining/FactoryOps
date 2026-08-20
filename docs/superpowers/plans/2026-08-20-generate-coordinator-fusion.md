# Coordinator Fusion Generation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 从明确的 Specialist Recommendation 集合生成并持久化可信 Coordinator Fusion。

**Architecture:** generation service 使用完整 reader 建立最小 provider context；provider 仅返回 draft；应用层构造确定性 Fusion 并由 persistence 在锁内重验 provenance 与来源。

**Tech Stack:** Python 3.10、SQLAlchemy、MySQL 8.4、pytest/Testcontainers、既有版本化 Contracts。

**Spec:** `openspec/changes/2026-08-20-generate-coordinator-fusion/design.md`

## Global Constraints

- 不修改 `dataset/`。
- 不执行 Risk、Approval 或 Business Action。
- TDD：每项生产行为必须先有可观察的失败测试。

---

### Task 1: Provider 与生成编排

**Files:**
- Create: `services/agent-service/src/factoryops_agent_service/coordinator_fusion_generation.py`
- Test: `services/agent-service/tests/test_coordinator_fusion_generation_mysql.py`

**Interfaces:**
- Consumes: `CoordinatorFusionService.save`, `SpecialistRecommendationService.get_by_key`, lifecycle Execution reader。
- Produces: `CoordinatorFusionGenerationService.generate(command, provider)`。

- [ ] 写 recorded provider 隔离、成功生成、replay、拒绝路径与真实并发失败测试。
- [ ] 运行局部测试，确认因 generation 模块不存在而 RED。
- [ ] 实现 context/draft/provider 与 generation service。
- [ ] 运行局部测试至 GREEN。

### Task 2: 保存期 provenance fencing

**Files:**
- Modify: `services/agent-service/src/factoryops_agent_service/coordinator_fusion.py`
- Test: `services/agent-service/tests/test_coordinator_fusion_generation_mysql.py`

**Interfaces:**
- Consumes: generation 调用前的六项 Coordinator provenance。
- Produces: `CoordinatorFusionService.save(..., expected_execution_provenance=...)`。

- [ ] 写 provider 阻塞期间 provenance 漂移的真实 MySQL RED 测试。
- [ ] 在 Coordinator Execution 行锁后逐项重验 provenance。
- [ ] 运行 generation 与 Fusion persistence 测试至 GREEN。

### Task 3: 验证、审查与移交

**Files:**
- Modify: 当前 Change 的 `tasks.md`、`verification.md`、`review-handoff.md`、`proposal.md`。

**Interfaces:**
- Consumes: 最终实现与真实命令输出。
- Produces: `review-handoff-ready` stacked branch。

- [ ] 运行局部、相关 MySQL、Agent、Contract、Java、Ruff、diff、dataset 检查。
- [ ] 调用独立子 Agent 审查并修复全部 Critical/Important。
- [ ] 提交并推送 feature branch；不合并 main、不归档。
