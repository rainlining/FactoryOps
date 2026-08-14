package com.factoryops.business.outbox.publisher;

public final class OutboxPublicationStateException extends RuntimeException {
  public OutboxPublicationStateException(String eventId, int affectedRows) {
    super("Expected one PENDING outbox row for " + eventId + " but updated " + affectedRows);
  }
}
