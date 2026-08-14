package com.factoryops.business.outbox.publisher;

import static org.assertj.core.api.Assertions.assertThat;

import ch.qos.logback.classic.Logger;
import ch.qos.logback.classic.spi.ILoggingEvent;
import ch.qos.logback.core.read.ListAppender;
import com.factoryops.business.outbox.domain.OutboxEvent;
import java.time.Instant;
import java.util.List;
import org.junit.jupiter.api.Test;
import org.slf4j.LoggerFactory;

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
    assertThat(summary).isEqualTo(new PublicationRoundSummary(1, 1, 0, 2L));
  }

  @Test
  void includes_last_successful_offset_when_round_publishes_event() {
    var appender = attachPublisherAppender();
    try {
      var repository = repositoryReturning(event());
      var service =
          new OutboxPublicationService(
              ignored -> new KafkaPublication(1, 2, java.time.Duration.ZERO), repository);

      new ScheduledOutboxPublisher(repository, service, new OutboxPublisherProperties()).runOnce();

      assertThat(appender.list)
          .filteredOn(
              event -> event.getLoggerName().equals(ScheduledOutboxPublisher.class.getName()))
          .anySatisfy(
              event -> assertThat(event.getFormattedMessage()).contains("last_successful_offset=2"));
    } finally {
      detachPublisherAppender(appender);
    }
  }

  @Test
  void omits_last_successful_offset_when_round_has_no_success() {
    var appender = attachPublisherAppender();
    try {
      var repository = repositoryReturning(event());
      var service =
          new OutboxPublicationService(
              ignored -> {
                throw new IllegalStateException("broker unavailable");
              },
              repository);

      new ScheduledOutboxPublisher(repository, service, new OutboxPublisherProperties()).runOnce();

      assertThat(appender.list)
          .filteredOn(
              event -> event.getLoggerName().equals(ScheduledOutboxPublisher.class.getName()))
          .noneSatisfy(
              event -> assertThat(event.getFormattedMessage()).contains("last_successful_offset="));
    } finally {
      detachPublisherAppender(appender);
    }
  }

  private OutboxPublicationRepository repositoryReturning(OutboxEvent event) {
    return new OutboxPublicationRepository() {
      @Override
      public List<OutboxEvent> findPublishable(int limit) {
        return List.of(event);
      }

      @Override
      public Instant markPublished(String eventId) {
        return Instant.EPOCH;
      }
    };
  }

  private ListAppender<ILoggingEvent> attachPublisherAppender() {
    var logger = (Logger) LoggerFactory.getLogger(ScheduledOutboxPublisher.class);
    var appender = new ListAppender<ILoggingEvent>();
    appender.start();
    logger.addAppender(appender);
    return appender;
  }

  private void detachPublisherAppender(ListAppender<ILoggingEvent> appender) {
    var logger = (Logger) LoggerFactory.getLogger(ScheduledOutboxPublisher.class);
    logger.detachAppender(appender);
    appender.stop();
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
