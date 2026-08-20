# Approval Action Target Binding Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Bind every new executable Human Approval to the immutable Quality Incident of its Agent Run.

**Architecture:** Publish Approval v1.1 with incident identity, validate it against Risk+Run, persist the typed binding in Agent MySQL, and require it at Java intake while preserving v1.0 reads.

**Tech Stack:** Python/jsonschema/SQLAlchemy/MySQL; Java 17/Spring JDBC/Flyway/MySQL.

**Spec:** `openspec/changes/2026-08-20-bind-approval-action-target/design.md`

## Global Constraints

- Do not modify `dataset/`.
- Preserve v1.0 historical read/replay.
- No business action, Kafka event, or Workflow advancement.
- Follow TDD and commit each independently verified boundary.

---

### Task 1: Human Approval v1.1 Contract

**Files:** create `contracts/human_approval/v1.1.0/schema.json`; modify validator/tests/fixtures.

**Interfaces:** `validate_human_approval(payload, risk_decision, source_run=None)` validates v1.1 against both sources; canonical/relation support 1.0.0 and 1.1.0.

- [ ] Write tests that v1.1 succeeds only with matching Run identity/incident and fails on substitution or missing source.
- [ ] Run `python -m pytest -q contracts/human_approval/tests` and confirm RED.
- [ ] Add schema, fixture and minimal version-aware validator.
- [ ] Re-run and confirm GREEN; commit Contract boundary.

### Task 2: Agent persistence binding

**Files:** create migration 015; modify migration runner, `human_approval.py`, MySQL tests and migration expectations.

**Interfaces:** v1.1 current rows contain `incident_id`; save/get lock and validate `agent_runs` source.

- [ ] Add real MySQL tests for valid v1.1, wrong incident rollback, typed corruption and Run lock/concurrent drift; confirm RED.
- [ ] Add migration 015 and persistence locking/decoding with no lock-order regression.
- [ ] Run Approval + lifecycle migration suites and confirm GREEN; commit persistence boundary.

### Task 3: Java executable intake

**Files:** create Flyway V7; add v1.1 schema resource; modify validator/service/HTTP tests.

**Interfaces:** internal create requires contract `1.1.0`; `business_approvals.incident_id` is typed and integrity-checked; get can decode v1.0 legacy.

- [ ] Add HTTP/MySQL tests for v1.1 create/query, v1.0 create rejection and incident typed corruption; confirm RED.
- [ ] Add migration/resource/version-aware validator and service projection.
- [ ] Run `mvn -q -Dtest=HumanApprovalHttpIT test` and confirm GREEN; commit Java boundary.

### Task 4: Verification and review

**Files:** update OpenSpec verification/review-handoff/tasks/proposal.

- [ ] Run Contract full, Agent local/full, Java verify, Ruff, diff-check and dataset check.
- [ ] Dispatch independent read-only reviewer; fix every Critical/Important with regression tests and request re-review.
- [ ] Record exact results, commit, push stacked branch, and stop at review-handoff-ready.
