# Define Agent Run Contract Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 建立严格版本化的 Workflow Run v1.0.0 Contract，冻结 original/replay 身份、Provenance、Lifecycle 与关系分类语义。

**Architecture:** 使用 JSON Schema Draft 2020-12 负责结构、类型、枚举和条件字段，使用小型 Python Validator 负责版本前置与跨字段不变量。有效/无效 fixtures 是可执行示例，relation classifier 只对已验证快照进行 canonical 比较。

**Tech Stack:** Python 3、标准库 `unittest`、`jsonschema`、JSON Schema Draft 2020-12。

## Global Constraints

- Change ID 固定为 `2026-08-15-define-agent-run-contract`，学习等级为 `deep`。
- 本 Change 只实现 Contract，不创建 MySQL、Kafka、Agent Runtime 或 Java/Python 服务脚手架。
- Contract 版本固定为 `1.0.0`，所有对象使用严格未知字段策略。
- Evaluation ground truth 不得进入 Agent 可读取 Contract。
- 所有面向项目所有者的文档使用中文；代码保持格式化和可 review。
- 不修改或提交 `dataset/`。

---

### Task 1: Schema 与有效 Fixtures

**Files:**
- Create: `contracts/agent_run/__init__.py`
- Create: `contracts/agent_run/v1.0.0/schema.json`
- Create: `contracts/agent_run/fixtures/valid/original-run.json`
- Create: `contracts/agent_run/fixtures/valid/replay-run.json`
- Create: `contracts/agent_run/tests/__init__.py`
- Create: `contracts/agent_run/tests/test_schema.py`

**Interfaces:**
- Consumes: JSON Schema Draft 2020-12 and approved OpenSpec fields.
- Produces: valid original/replay documents and a strict v1.0.0 Schema used by Validator.

- [ ] **Step 1: Write failing Schema tests**

  Add tests that require the Schema file and validate both fixtures, plus assertions that every object node declares `additionalProperties: false`.

- [ ] **Step 2: Verify RED**

  Run: `python -m unittest contracts.agent_run.tests.test_schema -v`

  Expected: FAIL because `contracts/agent_run/v1.0.0/schema.json` and fixtures do not exist.

- [ ] **Step 3: Add minimal Schema and fixtures**

  Define strict `identity`, `provenance`, `lifecycle`, `execution_refs`, `progress` objects; use `if/then` branches for original/replay and terminal/non-terminal required fields.

- [ ] **Step 4: Verify GREEN**

  Run: `python -m unittest contracts.agent_run.tests.test_schema -v`

  Expected: all Schema tests PASS.

- [ ] **Step 5: Commit**

  Commit message: `feat(contract): define workflow run schema`

### Task 2: Validator 与失败边界

**Files:**
- Create: `contracts/agent_run/validator.py`
- Create: `contracts/agent_run/tests/test_validator.py`
- Create: `contracts/agent_run/fixtures/invalid/unsupported-version.json`
- Create: `contracts/agent_run/fixtures/invalid/ground-truth-leak.json`
- Create: `contracts/agent_run/fixtures/invalid/original-run-id-mismatch.json`
- Create: `contracts/agent_run/fixtures/invalid/original-with-replay-request.json`
- Create: `contracts/agent_run/fixtures/invalid/replay-missing-source.json`
- Create: `contracts/agent_run/fixtures/invalid/replay-self-reference.json`
- Create: `contracts/agent_run/fixtures/invalid/unknown-status.json`
- Create: `contracts/agent_run/fixtures/invalid/terminal-without-ended-at.json`
- Create: `contracts/agent_run/fixtures/invalid/non-terminal-with-ended-at.json`
- Create: `contracts/agent_run/fixtures/invalid/ended-before-started.json`
- Create: `contracts/agent_run/fixtures/invalid/completed-count-exceeds-total.json`

**Interfaces:**
- Consumes: `v1.0.0/schema.json` and fixture documents.
- Produces: `validate_run(run, supported_versions=("1.0.0",)) -> None`, `AgentRunValidationError`, stable `ValidationIssue` objects.

- [ ] **Step 1: Write failing Validator tests**

  Assert stable error code and JSON path for version, Schema, original identity, replay self-reference, timestamp ordering and progress count failures.

- [ ] **Step 2: Verify RED**

  Run: `python -m unittest contracts.agent_run.tests.test_validator.AgentRunValidationTest -v`

  Expected: FAIL because `validator.py` is absent.

- [ ] **Step 3: Implement minimal Validator**

  Load only explicitly supported versions, map first Schema error to JSON path, then validate original identity equality, replay self-references, timestamp ordering and completed count.

- [ ] **Step 4: Verify GREEN**

  Run: `python -m unittest contracts.agent_run.tests.test_validator.AgentRunValidationTest -v`

  Expected: all Validator tests PASS.

- [ ] **Step 5: Commit**

  Commit message: `feat(contract): validate workflow run invariants`

### Task 3: Canonical Relation Classifier

**Files:**
- Modify: `contracts/agent_run/validator.py`
- Modify: `contracts/agent_run/tests/test_validator.py`

**Interfaces:**
- Consumes: two Workflow Run mappings accepted by `validate_run`.
- Produces: `canonicalize_run(run) -> bytes` and `classify_run_relation(first, second) -> str`.

- [ ] **Step 1: Write failing relation tests**

  Cover key-order independence, `duplicate-identical`, `duplicate-conflicting`, `distinct`, and invalid-input rejection before classification.

- [ ] **Step 2: Verify RED**

  Run: `python -m unittest contracts.agent_run.tests.test_validator.AgentRunRelationTest -v`

  Expected: FAIL because relation functions are absent.

- [ ] **Step 3: Implement minimal canonicalization and classification**

  Canonicalize with sorted keys, compact separators, UTF-8 and `allow_nan=False`; validate both inputs before comparing `run_id` and canonical bytes.

- [ ] **Step 4: Verify GREEN and regression**

  Run: `python -m unittest contracts.agent_run.tests.test_validator -v`

  Expected: all Agent Run Validator and relation tests PASS.

- [ ] **Step 5: Commit**

  Commit message: `feat(contract): classify workflow run duplicates`

### Task 4: Documentation, Full Verification and Handoff

**Files:**
- Create: `contracts/agent_run/README.md`
- Modify: `openspec/changes/2026-08-15-define-agent-run-contract/tasks.md`
- Modify: `openspec/changes/2026-08-15-define-agent-run-contract/verification.md`
- Modify: `openspec/changes/2026-08-15-define-agent-run-contract/review-handoff.md`

**Interfaces:**
- Consumes: completed Schema, Validator, fixtures, tests and Git history.
- Produces: owner-facing Contract reference and independent Review/Learning handoff.

- [ ] **Step 1: Write Contract README**

  Document object boundary, fields, original/replay examples, validation order, non-goals and consumer rules in Chinese.

- [ ] **Step 2: Run focused and regression verification**

  Run: `python -m unittest discover -s contracts -p "test_*.py" -v`

  Run: `git diff --check`

  Run: `git status --short`

  Expected: all Contract tests PASS; diff check has no output; only Change-scoped files are modified.

- [ ] **Step 3: Record evidence and handoff**

  Replace provisional verification/handoff text with actual commands, counts, commits, walkthrough symbols, limitations, owner task, failure exercise and recovery commands.

- [ ] **Step 4: Commit and push**

  Commit message: `docs: prepare agent run contract review handoff`

  Push branch `codex/define-agent-run-contract` and stop at `review-handoff-ready`; do not merge `main`.
