# Persist Agent Run Lifecycle Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 用 MySQL 8.4、显式事务和乐观锁持久化 Workflow Run 当前快照与 append-only transition 历史。

**Architecture:** Agent Service 新增 `run_lifecycle` 模块；纯领域规则与 SQLAlchemy Core Repository 分离。Migration runner 有序应用 Agent DB migrations，Repository 用短事务完成原子创建和迁移，失败后用新事务分类重复与并发冲突。

**Tech Stack:** Python 3.10+、SQLAlchemy Core 2.x、PyMySQL、MySQL 8.4、pytest、testcontainers、JSON Schema Draft 2020-12。

## Global Constraints

- Change ID 为 `2026-08-15-persist-agent-run-lifecycle`，学习等级 `deep`。
- 不连接 Kafka Worker、HTTP、Coordinator、LLM、Tool 或 Java Business DB。
- 不在事务内调用任何外部服务。
- identity/provenance 不得出现在状态迁移 UPDATE 中。
- 所有时间由一次可注入 UTC Clock 产生并以微秒精度保存。
- 不修改或提交 `dataset/`。

---

### Task 1: Contract 取消时间语义

**Files:**
- Modify: `contracts/agent_run/v1.0.0/schema.json`
- Modify: `contracts/agent_run/tests/test_validator.py`

**Interfaces:**
- Consumes: Workflow Run v1.0.0 lifecycle status and timestamps.
- Produces: CANCELLED may omit `started_at`; SUCCEEDED/FAILED still require it.

- [ ] 先写 `PENDING → CANCELLED` 快照通过和 `FAILED` 缺 started_at 拒绝测试，观察前者 RED。
- [ ] 最小修改 Schema 条件分支并运行 Agent Run Contract tests 转 GREEN。
- [ ] 运行全部 Contract 回归并提交 `fix(contract): allow cancellation before run start`。

### Task 2: Domain Model 与迁移规则

**Files:**
- Create: `services/agent-service/src/factoryops_agent_service/run_lifecycle/__init__.py`
- Create: `services/agent-service/src/factoryops_agent_service/run_lifecycle/model.py`
- Create: `services/agent-service/src/factoryops_agent_service/run_lifecycle/rules.py`
- Create: `services/agent-service/tests/test_run_lifecycle_rules.py`

**Interfaces:**
- Produces immutable create/transition commands, outcome/result enums, legal transition validation and lifecycle timestamp calculation.

- [ ] 先写状态图、终态、Suspended Checkpoint、首次 started_at、启动前取消和 reason tests，观察 import RED。
- [ ] 实现最小 enums/dataclasses/rules 并转 GREEN。
- [ ] Ruff + pytest 后提交 `feat(agent): define run lifecycle rules`。

### Task 3: Agent DB Migration

**Files:**
- Modify: `services/agent-service/src/factoryops_agent_service/event_ingress/migration.py`
- Create: `services/agent-service/src/factoryops_agent_service/event_ingress/migrations/002_create_agent_run_lifecycle.sql`
- Create: `services/agent-service/tests/test_run_lifecycle_mysql.py`

**Interfaces:**
- Produces ordered migration application and Run/Transition tables with constraints and indexes.

- [ ] 先写 MySQL test 要求 001+002 history、表、索引、外键和 CHECK，观察 RED。
- [ ] 将 runner 改为显式有序 migration tuple，新增 002 SQL 并转 GREEN。
- [ ] 验证对已应用 001 的数据库只补 002，提交 `feat(agent): migrate run lifecycle schema`。

### Task 4: Creation 与读取

**Files:**
- Create: `services/agent-service/src/factoryops_agent_service/run_lifecycle/repository.py`
- Create: `services/agent-service/src/factoryops_agent_service/run_lifecycle/service.py`
- Modify: `services/agent-service/tests/test_run_lifecycle_mysql.py`

**Interfaces:**
- Produces `create_original_run`, `create_replay_run`, `get_run` and structured creation outcomes.

- [ ] 先写 original 原子创建、Inbox FK、identical/conflicting、replay 血缘和 Contract 重建测试，观察 RED。
- [ ] 实现 service-generated IDs/Clock、显式创建事务和失败后新事务分类。
- [ ] 运行 MySQL suite 后提交 `feat(agent): persist original and replay runs`。

### Task 5: 状态迁移

**Files:**
- Modify: `services/agent-service/src/factoryops_agent_service/run_lifecycle/repository.py`
- Modify: `services/agent-service/src/factoryops_agent_service/run_lifecycle/service.py`
- Modify: `services/agent-service/tests/test_run_lifecycle_mysql.py`

**Interfaces:**
- Produces `transition_run` with applied, duplicate-identical, duplicate-conflicting and concurrency-conflict outcomes.

- [ ] 先写合法迁移、非法迁移、request duplicate/conflict、过期 revision、Suspended 与时间测试，观察 RED。
- [ ] 实现 expected status/revision UPDATE、同事务 history INSERT 和回滚后新事务分类。
- [ ] 增加两个并发命令测试并提交 `feat(agent): persist idempotent run transitions`。

### Task 6: Failure Evidence、Docs 与 Handoff

**Files:**
- Modify: `services/agent-service/README.md`
- Modify: `openspec/changes/2026-08-15-persist-agent-run-lifecycle/tasks.md`
- Modify: `openspec/changes/2026-08-15-persist-agent-run-lifecycle/verification.md`
- Modify: `openspec/changes/2026-08-15-persist-agent-run-lifecycle/review-handoff.md`

**Interfaces:**
- Produces reproducible verification and independent Review/Learning handoff.

- [ ] 增加 transition INSERT 故障后 snapshot 回滚测试。
- [ ] 运行 Ruff、Agent unit/MySQL、Contract 全量、`git diff --check` 和 scope 检查。
- [ ] 填写真实 commits、调用链、测试数量、已知限制、Owner 任务和两项故障实验。
- [ ] 推送 `codex/persist-agent-run-lifecycle` 并停在 `review-handoff-ready`，不得合并 main。
