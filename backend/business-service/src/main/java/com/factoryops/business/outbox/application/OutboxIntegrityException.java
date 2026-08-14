package com.factoryops.business.outbox.application;

public final class OutboxIntegrityException extends RuntimeException {
  public OutboxIntegrityException(String eventId, String reason) {
    super("Outbox integrity failure for " + eventId + ": " + reason);
  }
}
