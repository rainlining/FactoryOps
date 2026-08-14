package com.factoryops.business.outbox.application;

import static org.assertj.core.api.Assertions.assertThat;

import com.factoryops.business.outbox.domain.OutboxEvent;
import java.nio.charset.StandardCharsets;
import java.time.Instant;
import org.junit.jupiter.api.Test;

class OutboxEventViewTest {
  @Test
  void calculates_payload_size_in_utf8_bytes() {
    var payload = "{\"message\":\"异常\"}";
    var event =
        new OutboxEvent(
            "EVT-" + "A".repeat(64),
            "quality-incident",
            "QI-" + "B".repeat(64),
            "quality.incident.opened",
            "1.0",
            "factoryops.quality.incident.v1",
            "QI-" + "B".repeat(64),
            Instant.EPOCH,
            payload,
            "PENDING",
            0,
            Instant.EPOCH,
            null,
            null,
            Instant.EPOCH);

    var view = OutboxEventView.from(event);

    assertThat(view.payloadSizeBytes())
        .isEqualTo(payload.getBytes(StandardCharsets.UTF_8).length);
    assertThat(view.payloadSizeBytes()).isGreaterThan(payload.length());
  }
}
