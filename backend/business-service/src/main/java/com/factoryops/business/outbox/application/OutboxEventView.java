package com.factoryops.business.outbox.application;

import com.factoryops.business.outbox.domain.OutboxEvent;
import java.nio.charset.StandardCharsets;

public record OutboxEventView(OutboxEvent event, long payloadSizeBytes) {
  public static OutboxEventView from(OutboxEvent event) {
    return new OutboxEventView(
        event, event.payload().getBytes(StandardCharsets.UTF_8).length);
  }
}
