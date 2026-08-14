package com.factoryops.business.outbox.infrastructure;

import com.factoryops.business.inspection.infrastructure.InspectionJdbcRepository;
import com.factoryops.business.outbox.application.OutboxEventView;
import com.factoryops.business.outbox.application.OutboxIntegrityException;
import com.factoryops.business.outbox.domain.OutboxEvent;
import com.factoryops.business.outbox.publisher.OutboxPublicationRepository;
import com.factoryops.business.outbox.publisher.OutboxPublicationStateException;
import java.sql.ResultSet;
import java.sql.SQLException;
import java.time.Instant;
import java.util.ArrayList;
import java.util.List;
import java.util.Optional;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.stereotype.Repository;
import org.springframework.transaction.annotation.Transactional;

@Repository
public class OutboxEventJdbcRepository implements OutboxPublicationRepository {
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
            this::map,
            eventId)
        .stream()
        .findFirst();
  }

  @Override
  public List<OutboxEvent> findPublishable(int limit) {
    if (limit <= 0) {
      throw new IllegalArgumentException("limit must be positive");
    }
    return jdbc.query(
        """
        SELECT event_id, aggregate_type, aggregate_id, event_type,
               contract_version, topic, message_key, occurred_at, payload,
               status, attempt_count, available_at, published_at,
               last_error, created_at
        FROM outbox_events
        WHERE status = 'PENDING'
          AND available_at <= CURRENT_TIMESTAMP(6)
        ORDER BY available_at, created_at, event_id
        LIMIT ?
        """,
        this::map,
        limit);
  }

  @Override
  @Transactional
  public Instant markPublished(String eventId) {
    var affected =
        jdbc.update(
            """
            UPDATE outbox_events
            SET status = 'PUBLISHED', published_at = CURRENT_TIMESTAMP(6)
            WHERE event_id = ? AND status = 'PENDING'
            """,
            eventId);
    if (affected != 1) {
      throw new OutboxPublicationStateException(eventId, affected);
    }
    return jdbc.queryForObject(
        "SELECT published_at FROM outbox_events WHERE event_id = ?",
        (row, number) -> row.getTimestamp(1).toInstant(),
        eventId);
  }

  public Optional<OutboxEventView> findViewByEventId(String eventId) {
    return findByEventId(eventId).map(OutboxEventView::from);
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

  private List<String> immutableMismatches(OutboxEvent actual, OutboxEvent expected) {
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
      List<String> mismatches, String field, Object actual, Object expected) {
    if (!actual.equals(expected)) {
      mismatches.add(field);
    }
  }

  private OutboxEvent map(ResultSet row, int number) throws SQLException {
    return new OutboxEvent(
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
        row.getTimestamp("created_at").toInstant());
  }
}
