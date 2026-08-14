package com.factoryops.business.outbox.publisher;

import org.springframework.boot.autoconfigure.condition.ConditionalOnProperty;
import org.springframework.boot.context.properties.EnableConfigurationProperties;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;
import org.springframework.kafka.core.KafkaTemplate;
import org.springframework.scheduling.annotation.EnableScheduling;

@Configuration
@EnableScheduling
@EnableConfigurationProperties(OutboxPublisherProperties.class)
public class OutboxPublisherConfiguration {
  @Bean
  @ConditionalOnProperty(name = "factoryops.outbox.publisher.enabled", havingValue = "true")
  KafkaOutboxEventSender kafkaOutboxEventSender(
      KafkaTemplate<String, byte[]> kafka, OutboxPublisherProperties properties) {
    return new KafkaOutboxEventSender(kafka, properties);
  }

  @Bean
  @ConditionalOnProperty(name = "factoryops.outbox.publisher.enabled", havingValue = "true")
  OutboxPublicationService outboxPublicationService(
      OutboxEventSender sender, OutboxPublicationRepository repository) {
    return new OutboxPublicationService(sender, repository);
  }

  @Bean
  @ConditionalOnProperty(name = "factoryops.outbox.publisher.enabled", havingValue = "true")
  ScheduledOutboxPublisher scheduledOutboxPublisher(
      OutboxPublicationRepository repository,
      OutboxPublicationService service,
      OutboxPublisherProperties properties) {
    return new ScheduledOutboxPublisher(repository, service, properties);
  }
}
