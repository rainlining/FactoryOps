# Outbox Round Success Offset Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add `last_successful_offset` to Publisher round logs only when at least one event completes both Kafka acknowledgement and the PUBLISHED database update.

**Architecture:** Carry the last confirmed Kafka offset from `OutboxPublicationService` into `PublicationRoundSummary`. `ScheduledOutboxPublisher` chooses a log shape with or without the field based on whether the summary contains an offset. No Outbox table, event payload, Kafka contract, or publication order changes.

**Tech Stack:** Java 17, JUnit 5, AssertJ, Spring Kafka, SLF4J, Maven.

## Global Constraints

- Kafka acknowledgement must precede the PENDING → PUBLISHED database update.
- `last_successful_offset` is recorded only after both operations succeed.
- The field must be absent from a round log when no event succeeds.
- Do not modify the Outbox table or canonical event payload.
- `dataset/` must remain untouched.

---

### Task 1: Define the round summary behavior

**Files:**
- Modify: `backend/business-service/src/main/java/com/factoryops/business/outbox/publisher/PublicationRoundSummary.java`
- Modify: `backend/business-service/src/main/java/com/factoryops/business/outbox/publisher/OutboxPublicationService.java`
- Test: `backend/business-service/src/test/java/com/factoryops/business/outbox/publisher/OutboxPublicationServiceTest.java`

**Interfaces:**
- `PublicationRoundSummary` produces `Long lastSuccessfulOffset`, which is `null` when no event completes publication.
- `OutboxPublicationService.publish(List<OutboxEvent>)` returns the last successful `KafkaPublication.offset()` only after `repository.markPublished(event.eventId())` returns successfully.

- [ ] **Step 1: Write the failing test**

Add one test that publishes two successful events and asserts the summary contains the second event's Kafka offset; add one test that fails all sends and asserts the offset is `null`.

- [ ] **Step 2: Run the focused test and verify it fails**

Run from `backend/business-service`:

```powershell
mvn "-Dtest=OutboxPublicationServiceTest" "-DfailIfNoTests=false" test
```

Expected: compilation or assertion failure because `PublicationRoundSummary` has no `lastSuccessfulOffset` behavior.

- [ ] **Step 3: Implement the minimal summary propagation**

Add the nullable field and update the service as follows:

```java
Long lastSuccessfulOffset = null;
// after send and markPublished both succeed:
lastSuccessfulOffset = publication.offset();
return new PublicationRoundSummary(events.size(), published, failed, lastSuccessfulOffset);
```

- [ ] **Step 4: Run the focused test and verify it passes**

Run the same Maven command and expect all `OutboxPublicationServiceTest` tests to pass.

- [ ] **Step 5: Commit the independently testable change**

```powershell
git add backend/business-service/src/main/java/com/factoryops/business/outbox/publisher/PublicationRoundSummary.java backend/business-service/src/main/java/com/factoryops/business/outbox/publisher/OutboxPublicationService.java backend/business-service/src/test/java/com/factoryops/business/outbox/publisher/OutboxPublicationServiceTest.java
git commit -m "feat: track last successful outbox offset"
```

### Task 2: Emit the field conditionally in the round log

**Files:**
- Modify: `backend/business-service/src/main/java/com/factoryops/business/outbox/publisher/ScheduledOutboxPublisher.java`
- Test: `backend/business-service/src/test/java/com/factoryops/business/outbox/publisher/ScheduledOutboxPublisherTest.java`

**Interfaces:**
- `ScheduledOutboxPublisher.runOnce()` returns the unchanged `PublicationRoundSummary` and emits `last_successful_offset` only when `summary.lastSuccessfulOffset() != null`.

- [ ] **Step 1: Write the failing log assertion**

Capture the logger output for a successful round and an all-failed round. Assert that only the successful round contains `last_successful_offset=` and that its value equals the last successful offset.

- [ ] **Step 2: Run the focused test and verify it fails**

```powershell
mvn "-Dtest=ScheduledOutboxPublisherTest" "-DfailIfNoTests=false" test
```

Expected: failure because the current summary log never includes `last_successful_offset`.

- [ ] **Step 3: Implement conditional logging**

Use one log format when the offset is `null` and a second format containing `last_successful_offset={}` when it is non-null. Keep `selected`, `published`, `failed`, and duration in both formats.

- [ ] **Step 4: Run focused, full, and contract verification**

```powershell
mvn "-Dtest=OutboxPublicationServiceTest,ScheduledOutboxPublisherTest" "-DfailIfNoTests=false" test
mvn verify
python -m unittest discover -s contracts -t . -v
git diff --check
```

Expected: all Java unit/integration tests and all Python Contract tests pass; diff check passes; `dataset/` is absent from the diff.

- [ ] **Step 5: Commit the log change**

```powershell
git add backend/business-service/src/main/java/com/factoryops/business/outbox/publisher/ScheduledOutboxPublisher.java backend/business-service/src/test/java/com/factoryops/business/outbox/publisher/ScheduledOutboxPublisherTest.java
git commit -m "feat: log last successful outbox offset"
```

## Manual Kafka Learning Verification

After the code verification, start `infra/kafka/compose.yml`, open Kafbat UI at `http://localhost:8090`, publish an Outbox event, and compare:

```text
MySQL PENDING → Kafka record Key/Partition/Offset/Payload → MySQL PUBLISHED
```

For the failure exercise, force the first `markPublished` call to fail, then run the Publisher again and observe two records with the same Key/Payload and different Offset values before the database reaches `PUBLISHED`.
