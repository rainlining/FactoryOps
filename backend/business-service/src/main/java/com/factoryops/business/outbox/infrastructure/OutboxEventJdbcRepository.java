package com.factoryops.business.outbox.infrastructure;

import com.factoryops.business.inspection.infrastructure.InspectionJdbcRepository;
import com.factoryops.business.outbox.application.OutboxIntegrityException;
import com.factoryops.business.outbox.domain.OutboxEvent;
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
    return jdbc.query(
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
        eventId).stream().findFirst();
  }

  public void requireMatching(OutboxEvent expected) {
    var actual =
        findByEventId(expected.eventId())
            .orElseThrow(
                () -> new OutboxIntegrityException(expected.eventId(), "event is missing"));
    if (!sameImmutableEvent(actual, expected)) {
      throw new OutboxIntegrityException(expected.eventId(), "stored event content conflicts");
    }
  }

  private boolean sameImmutableEvent(OutboxEvent actual, OutboxEvent expected) {
    return actual.eventId().equals(expected.eventId())
        && actual.aggregateType().equals(expected.aggregateType())
        && actual.aggregateId().equals(expected.aggregateId())
        && actual.eventType().equals(expected.eventType())
        && actual.contractVersion().equals(expected.contractVersion())
        && actual.topic().equals(expected.topic())
        && actual.messageKey().equals(expected.messageKey())
        && actual.occurredAt().equals(expected.occurredAt())
        && actual.payload().equals(expected.payload());
  }
}
