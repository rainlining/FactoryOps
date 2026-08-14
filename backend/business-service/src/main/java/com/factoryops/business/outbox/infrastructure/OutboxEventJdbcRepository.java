package com.factoryops.business.outbox.infrastructure;

import com.factoryops.business.inspection.infrastructure.InspectionJdbcRepository;
import com.factoryops.business.outbox.application.OutboxIntegrityException;
import com.factoryops.business.outbox.domain.OutboxEvent;
import java.util.ArrayList;
import java.util.Optional;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.stereotype.Repository;

@Repository
public class OutboxEventJdbcRepository {
  private final JdbcTemplate jdbc;

  public OutboxEventJdbcRepository(JdbcTemplate jdbc) {
    this.jdbc = jdbc;
  }

  public void insert(OutboxEvent event) {
    jdbc.update(
        """
        INSERT INTO outbox_events (
          event_id, aggregate_type, aggregate_id_hash, aggregate_id,
          event_type, contract_version, topic, message_key, occurred_at,
          payload, status, attempt_count, available_at, published_at,
          last_error, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        event.eventId(),
        event.aggregateType(),
        InspectionJdbcRepository.hash(event.aggregateId()),
        event.aggregateId(),
        event.eventType(),
        event.contractVersion(),
        event.topic(),
        event.messageKey(),
        event.occurredAt(),
        event.payload(),
        event.status(),
        event.attemptCount(),
        event.availableAt(),
        event.publishedAt(),
        event.lastError(),
        event.createdAt());
  }

  public Optional<OutboxEvent> findByEventId(String eventId) {
    return jdbc
        .query(
            """
            SELECT event_id, aggregate_type, aggregate_id, event_type,
                   contract_version, topic, message_key, occurred_at, payload,
                   status, attempt_count, available_at, published_at,
                   last_error, created_at
            FROM outbox_events
            WHERE event_id = ?
            """,
            (row, number) ->
                new OutboxEvent(
                    row.getString("event_id"),
                    row.getString("aggregate_type"),
                    row.getString("aggregate_id"),
                    row.getString("event_type"),
                    row.getString("contract_version"),
                    row.getString("topic"),
                    row.getString("message_key"),
                    row.getTimestamp("occurred_at").toInstant(),
                    row.getString("payload"),
                    row.getString("status"),
                    row.getInt("attempt_count"),
                    row.getTimestamp("available_at").toInstant(),
                    row.getTimestamp("published_at") == null
                        ? null
                        : row.getTimestamp("published_at").toInstant(),
                    row.getString("last_error"),
                    row.getTimestamp("created_at").toInstant()),
            eventId)
        .stream()
        .findFirst();
  }

  public void requireMatching(OutboxEvent expected) {
    var actual =
        findByEventId(expected.eventId())
            .orElseThrow(
                () -> new OutboxIntegrityException(expected.eventId(), "event is missing"));
    var mismatches = immutableMismatches(actual, expected);
    if (!mismatches.isEmpty()) {
      throw new OutboxIntegrityException(
          expected.eventId(), "stored event content conflicts in " + String.join(", ", mismatches));
    }
  }

  private java.util.List<String> immutableMismatches(OutboxEvent actual, OutboxEvent expected) {
    var mismatches = new ArrayList<String>();
    addMismatch(mismatches, "event_id", actual.eventId(), expected.eventId());
    addMismatch(mismatches, "aggregate_type", actual.aggregateType(), expected.aggregateType());
    addMismatch(mismatches, "aggregate_id", actual.aggregateId(), expected.aggregateId());
    addMismatch(mismatches, "event_type", actual.eventType(), expected.eventType());
    addMismatch(
        mismatches, "contract_version", actual.contractVersion(), expected.contractVersion());
    addMismatch(mismatches, "topic", actual.topic(), expected.topic());
    addMismatch(mismatches, "message_key", actual.messageKey(), expected.messageKey());
    addMismatch(mismatches, "occurred_at", actual.occurredAt(), expected.occurredAt());
    addMismatch(mismatches, "payload", actual.payload(), expected.payload());
    return mismatches;
  }

  private void addMismatch(
      java.util.List<String> mismatches, String field, Object actual, Object expected) {
    if (!actual.equals(expected)) {
      mismatches.add(field);
    }
  }
}
