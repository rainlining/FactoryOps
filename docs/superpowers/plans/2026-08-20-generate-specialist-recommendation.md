# Generate Specialist Recommendation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 从真实 RUNNING Specialist Execution 调用受控 provider，构造并幂等持久化 Specialist Recommendation。

**Architecture:** generation service 在外部调用前做只读 parent preflight，provider 只返回 draft，应用层构造身份后复用 persistence 的事务 fencing。Recorded provider 以显式 role 配置提供可复现 demo 输出。

**Tech Stack:** Python 3、typing Protocol/dataclass、SQLAlchemy、MySQL 8.4 Testcontainers、pytest。

**Spec:** `openspec/changes/2026-08-20-generate-specialist-recommendation/design.md`

## Global Constraints

- 不修改 Recommendation Contract 或数据库 schema。
- Provider context 不包含 Evaluation ground truth。
- Provider 调用期间不持有数据库事务。
- 不推进 Task/Execution，不修改 `dataset/`。

---

### Task 1: Provider boundary 与 recorded provider

**Files:**
- Create: `services/agent-service/src/factoryops_agent_service/specialist_generation.py`
- Test: `services/agent-service/tests/test_specialist_generation_mysql.py`

**Interfaces:**
- Produces: `SpecialistGenerationContext`, `SpecialistRecommendationDraft`, `SpecialistRecommendationProvider.generate(context)`, `RecordedSpecialistProvider`。

- [ ] 写失败测试：recorded provider 按 role 返回隔离 draft，缺少 role 时明确拒绝。
- [ ] 运行测试，确认因模块不存在而 RED。
- [ ] 用 frozen dataclass、Protocol 和 `copy.deepcopy` 实现最小 provider 边界。
- [ ] 运行局部测试并确认 GREEN。

### Task 2: Generation service 与真实 MySQL fencing

**Files:**
- Modify: `services/agent-service/src/factoryops_agent_service/specialist_generation.py`
- Modify: `services/agent-service/tests/test_specialist_generation_mysql.py`

**Interfaces:**
- Consumes: `AgentExecutionLifecycleService.get_execution`, `AgentTaskLifecycleService.get_task`, `compute_recommendation_key`, `SpecialistRecommendationService.save`。
- Produces: `SpecialistRecommendationGenerationService.generate(command, provider)`。

- [ ] 写失败测试：RUNNING parent 生成合法 Recommendation，identity/key/ID 由 execution 确定。
- [ ] 写失败测试：replay 不调用 provider；provider exception/非法 draft/parent mismatch 不落库。
- [ ] 写失败测试：真实并发 identical 只留一行；provider 阻塞期间 parent 失效后保存被拒绝。
- [ ] 运行测试，确认缺少 generation service 的预期 RED。
- [ ] 实现 preflight、最小 context、replay short-circuit、provider error wrapping、payload build 与 persistence delegation。
- [ ] 运行局部测试并确认 GREEN。

### Task 3: 验证与 handoff

**Files:**
- Modify: `openspec/changes/2026-08-20-generate-specialist-recommendation/{proposal,tasks,verification,review-handoff}.md`

**Interfaces:**
- Consumes: 前两任务全部接口与测试。
- Produces: `review-handoff-ready` 分支。

- [ ] 运行 generation 局部、Recommendation/Execution/Task MySQL 回归、Agent 全量、Contract、Java verify、Ruff 和 diff/dataset checks。
- [ ] 填写实际结果，不复制预期数字。
- [ ] 提交实现并调用独立子 Agent；修复 Critical/Important 后由同一 Agent 复审。
- [ ] 更新最终 HEAD，提交并推送 `codex/generate-specialist-recommendation`。
