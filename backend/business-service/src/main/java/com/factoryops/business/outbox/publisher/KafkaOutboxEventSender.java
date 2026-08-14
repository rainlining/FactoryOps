package com.factoryops.business.outbox.publisher;

import com.factoryops.business.outbox.domain.OutboxEvent;
import java.nio.charset.StandardCharsets;
import java.time.Duration;
import java.util.concurrent.TimeUnit;
import org.apache.kafka.clients.producer.ProducerRecord;
import org.springframework.kafka.core.KafkaTemplate;

public final class KafkaOutboxEventSender implements OutboxEventSender {
  private final KafkaTemplate<String, byte[]> kafka;
  private final Duration deliveryTimeout;

  public KafkaOutboxEventSender(
      KafkaTemplate<String, byte[]> kafka, OutboxPublisherProperties properties) {
    this.kafka = kafka;
    this.deliveryTimeout = properties.getDeliveryTimeout();
  }

  @Override
  public KafkaPublication send(OutboxEvent event) throws Exception {
    long startedNanos = System.nanoTime();
    var record =
        new ProducerRecord<String, byte[]>(
            event.topic(), event.messageKey(), event.payload().getBytes(StandardCharsets.UTF_8));
    var result = kafka.send(record).get(deliveryTimeout.toMillis(), TimeUnit.MILLISECONDS);
    var metadata = result.getRecordMetadata();
    return new KafkaPublication(
        metadata.partition(),
        metadata.offset(),
        Duration.ofNanos(System.nanoTime() - startedNanos));
  }
}
