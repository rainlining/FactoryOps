package com.factoryops.business.outbox.publisher;

import static org.assertj.core.api.Assertions.assertThat;

import com.factoryops.business.outbox.domain.OutboxEvent;
import java.time.Instant;
import java.util.List;
import org.junit.jupiter.api.Test;

class ScheduledOutboxPublisherTest {
  @Test
  void uses_configured_batch_size_and_returns_round_summary() {
    var requested = new int[1];
    var event = event();
    OutboxPublicationRepository repository =
        new OutboxPublicationRepository() {
          @Override
          public List<OutboxEvent> findPublishable(int limit) {
            requested[0] = limit;
            return List.of(event);
          }

          @Override
          public Instant markPublished(String eventId) {
            return Instant.EPOCH;
          }
        };
    var properties = new OutboxPublisherProperties();
    properties.setBatchSize(7);
    var service =
        new OutboxPublicationService(
            ignored -> new KafkaPublication(1, 2, java.time.Duration.ZERO), repository);

    var summary = new ScheduledOutboxPublisher(repository, service, properties).runOnce();

    assertThat(requested[0]).isEqualTo(7);
    assertThat(summary).isEqualTo(new PublicationRoundSummary(1, 1, 0));
  }

  private OutboxEvent event() {
    return new OutboxEvent(
        "EVT-1",
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
