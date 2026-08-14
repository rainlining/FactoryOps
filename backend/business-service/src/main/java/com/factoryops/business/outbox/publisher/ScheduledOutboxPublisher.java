package com.factoryops.business.outbox.publisher;

import java.time.Duration;
import java.time.Instant;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.scheduling.annotation.Scheduled;

public final class ScheduledOutboxPublisher {
  private static final Logger log = LoggerFactory.getLogger(ScheduledOutboxPublisher.class);
  private final OutboxPublicationRepository repository;
  private final OutboxPublicationService service;
  private final int batchSize;

  public ScheduledOutboxPublisher(
      OutboxPublicationRepository repository,
      OutboxPublicationService service,
      OutboxPublisherProperties properties) {
    this.repository = repository;
    this.service = service;
    this.batchSize = properties.getBatchSize();
  }

  @Scheduled(fixedDelayString = "${factoryops.outbox.publisher.poll-delay:1s}")
  public PublicationRoundSummary runOnce() {
    var started = Instant.now();
    var summary = service.publish(repository.findPublishable(batchSize));
    var durationMillis = Duration.between(started, Instant.now()).toMillis();
    if (summary.lastSuccessfulOffset() == null) {
      log.info(
          "outbox_publish_round selected={} published={} failed={} duration_ms={}",
          summary.selected(),
          summary.published(),
          summary.failed(),
          durationMillis);
    } else {
      log.info(
          "outbox_publish_round selected={} published={} failed={} last_successful_offset={}"
              + " duration_ms={}",
          summary.selected(),
          summary.published(),
          summary.failed(),
          summary.lastSuccessfulOffset(),
          durationMillis);
    }
    return summary;
  }
}
