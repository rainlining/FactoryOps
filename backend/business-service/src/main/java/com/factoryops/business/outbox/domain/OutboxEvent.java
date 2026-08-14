package com.factoryops.business.outbox.domain;

import java.time.Instant;
import java.util.Objects;

public record OutboxEvent(
    String eventId,
    String aggregateType,
    String aggregateId,
    String eventType,
    String contractVersion,
    String topic,
    String messageKey,
    Instant occurredAt,
    String payload,
    String status,
    int attemptCount,
    Instant availableAt,
    Instant publishedAt,
    String lastError,
    Instant createdAt) {

  public OutboxEvent {
    requireText(eventId, "event_id");
    requireText(aggregateType, "aggregate_type");
    requireText(aggregateId, "aggregate_id");
    requireText(eventType, "event_type");
    requireText(contractVersion, "contract_version");
    requireText(topic, "topic");
    requireText(messageKey, "message_key");
    requireText(payload, "payload");
    Objects.requireNonNull(occurredAt, "occurred_at");
    Objects.requireNonNull(availableAt, "available_at");
    Objects.requireNonNull(createdAt, "created_at");
    if (attemptCount < 0) {
      throw new IllegalArgumentException("attempt_count must be non-negative");
    }
    if (!("PENDING".equals(status) && publishedAt == null)
        && !("PUBLISHED".equals(status) && publishedAt != null)) {
      throw new IllegalArgumentException("status and published_at are inconsistent");
    }
  }

  private static void requireText(String value, String field) {
    if (value == null || value.isBlank()) {
      throw new IllegalArgumentException(field + " is required");
    }
  }
}
