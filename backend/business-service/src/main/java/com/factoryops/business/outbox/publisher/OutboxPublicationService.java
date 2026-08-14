package com.factoryops.business.outbox.publisher;

import com.factoryops.business.outbox.domain.OutboxEvent;
import java.util.List;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;

public final class OutboxPublicationService {
  private static final Logger log = LoggerFactory.getLogger(OutboxPublicationService.class);

  private final OutboxEventSender sender;
  private final OutboxPublicationRepository repository;

  public OutboxPublicationService(
      OutboxEventSender sender, OutboxPublicationRepository repository) {
    this.sender = sender;
    this.repository = repository;
  }

  public PublicationRoundSummary publish(List<OutboxEvent> events) {
    var published = 0;
    var failed = 0;
    Long lastSuccessfulOffset = null;
    for (var event : events) {
      try {
        var publication = sender.send(event);
        repository.markPublished(event.eventId());
        published++;
        lastSuccessfulOffset = publication.offset();
        log.info(
            "outbox_publish_succeeded event_id={} topic={} message_key={} partition={} offset={}"
                + " ack_ms={}",
            event.eventId(),
            event.topic(),
            event.messageKey(),
            publication.partition(),
            publication.offset(),
            publication.acknowledgementLatency().toMillis());
      } catch (Exception failure) {
        failed++;
        log.error(
            "outbox_publish_failed event_id={} topic={} message_key={} failure_type={}",
            event.eventId(),
            event.topic(),
            event.messageKey(),
            failure.getClass().getSimpleName(),
            failure);
      }
    }
    return new PublicationRoundSummary(events.size(), published, failed, lastSuccessfulOffset);
  }
}
