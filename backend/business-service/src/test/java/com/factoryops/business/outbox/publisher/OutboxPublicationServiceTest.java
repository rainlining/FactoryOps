package com.factoryops.business.outbox.publisher;

import static org.assertj.core.api.Assertions.assertThat;

import com.factoryops.business.outbox.domain.OutboxEvent;
import java.time.Duration;
import java.time.Instant;
import java.util.ArrayList;
import java.util.List;
import org.junit.jupiter.api.Test;

class OutboxPublicationServiceTest {
  @Test
  void marks_only_acknowledged_events_and_continues_after_send_failure() {
    var calls = new ArrayList<String>();
    OutboxEventSender sender =
        event -> {
          calls.add("send:" + event.eventId());
          if (event.eventId().endsWith("1")) throw new IllegalStateException("broker unavailable");
          return new KafkaPublication(2, 17L, Duration.ofMillis(4));
        };
    OutboxPublicationRepository repository =
        eventId -> {
          calls.add("mark:" + eventId);
          return Instant.parse("2026-08-14T02:00:00Z");
        };
    var service = new OutboxPublicationService(sender, repository);

    var summary = service.publish(List.of(event("EVT-1"), event("EVT-2")));

    assertThat(calls).containsExactly("send:EVT-1", "send:EVT-2", "mark:EVT-2");
    assertThat(summary).isEqualTo(new PublicationRoundSummary(2, 1, 1, 17L));
    assertThat(summary.lastSuccessfulOffset()).isEqualTo(17L);
  }

  @Test
  void continues_after_database_update_failure() {
    var calls = new ArrayList<String>();
    OutboxEventSender sender = event -> new KafkaPublication(0, 1L, Duration.ZERO);
    OutboxPublicationRepository repository =
        eventId -> {
          calls.add(eventId);
          if (eventId.endsWith("1")) throw new IllegalStateException("database unavailable");
          return Instant.EPOCH;
        };

    var summary =
        new OutboxPublicationService(sender, repository)
            .publish(List.of(event("EVT-1"), event("EVT-2")));

    assertThat(calls).containsExactly("EVT-1", "EVT-2");
    assertThat(summary).isEqualTo(new PublicationRoundSummary(2, 1, 1, 1L));
    assertThat(summary.lastSuccessfulOffset()).isEqualTo(1L);
  }

  @Test
  void leaves_last_successful_offset_empty_when_no_event_completes() {
    OutboxEventSender sender =
        event -> {
          throw new IllegalStateException("broker unavailable");
        };
    OutboxPublicationRepository repository =
        eventId -> {
          throw new AssertionError("database must not be updated");
        };

    var summary =
        new OutboxPublicationService(sender, repository)
            .publish(List.of(event("EVT-1"), event("EVT-2")));

    assertThat(summary).isEqualTo(new PublicationRoundSummary(2, 0, 2, null));
    assertThat(summary.lastSuccessfulOffset()).isNull();
  }

  private OutboxEvent event(String id) {
    return new OutboxEvent(
        id,
        "quality-incident",
        "QI-1",
        "quality.incident.opened",
        "1.0",
        "factoryops.quality.incident.v1",
        "QI-1",
        Instant.EPOCH,
        "{}",
        "PENDING",
        0,
        Instant.EPOCH,
        null,
        null,
        Instant.EPOCH);
  }
}
