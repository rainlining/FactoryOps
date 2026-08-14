package com.factoryops.business.outbox.publisher;

import static java.nio.charset.StandardCharsets.UTF_8;
import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;

import com.factoryops.business.outbox.domain.OutboxEvent;
import java.time.Duration;
import java.time.Instant;
import java.util.List;
import java.util.Map;
import java.util.Properties;
import org.apache.kafka.clients.admin.AdminClient;
import org.apache.kafka.clients.admin.AdminClientConfig;
import org.apache.kafka.clients.admin.NewTopic;
import org.apache.kafka.clients.consumer.ConsumerConfig;
import org.apache.kafka.clients.consumer.KafkaConsumer;
import org.apache.kafka.clients.producer.ProducerConfig;
import org.apache.kafka.common.serialization.ByteArrayDeserializer;
import org.apache.kafka.common.serialization.ByteArraySerializer;
import org.apache.kafka.common.serialization.StringDeserializer;
import org.apache.kafka.common.serialization.StringSerializer;
import org.junit.jupiter.api.BeforeAll;
import org.junit.jupiter.api.Test;
import org.springframework.kafka.core.DefaultKafkaProducerFactory;
import org.springframework.kafka.core.KafkaTemplate;
import org.testcontainers.junit.jupiter.Container;
import org.testcontainers.junit.jupiter.Testcontainers;
import org.testcontainers.kafka.KafkaContainer;

@Testcontainers
class KafkaOutboxEventSenderIT {
  private static final String TOPIC = "factoryops.quality.incident.v1";

  @Container
  static final KafkaContainer KAFKA =
      new KafkaContainer("apache/kafka-native:4.1.0")
          .withEnv("KAFKA_AUTO_CREATE_TOPICS_ENABLE", "false");

  @BeforeAll
  static void createTopic() throws Exception {
    try (var admin =
        AdminClient.create(
            Map.of(AdminClientConfig.BOOTSTRAP_SERVERS_CONFIG, KAFKA.getBootstrapServers()))) {
      admin.createTopics(List.of(new NewTopic(TOPIC, 3, (short) 1))).all().get();
    }
  }

  @Test
  void sends_saved_key_and_exact_utf8_payload_to_real_kafka() throws Exception {
    var template = template();
    var properties = new OutboxPublisherProperties();
    properties.setDeliveryTimeout(Duration.ofSeconds(10));
    var payload = "{\"message\":\"中文\"}";

    var publication = new KafkaOutboxEventSender(template, properties).send(event(payload));

    try (var consumer = consumer()) {
      consumer.subscribe(List.of(TOPIC));
      var records = consumer.poll(Duration.ofSeconds(10));
      assertThat(records).hasSize(1);
      var record = records.iterator().next();
      assertThat(record.key()).isEqualTo("QI-1");
      assertThat(record.value()).isEqualTo(payload.getBytes(UTF_8));
      assertThat(publication.partition()).isEqualTo(record.partition());
      assertThat(publication.offset()).isEqualTo(record.offset());
    } finally {
      template.destroy();
    }
  }

  @Test
  void fails_instead_of_implicitly_creating_an_unknown_topic() {
    var template = template();
    var properties = new OutboxPublisherProperties();
    properties.setDeliveryTimeout(Duration.ofSeconds(2));

    try {
      assertThatThrownBy(
              () ->
                  new KafkaOutboxEventSender(template, properties)
                      .send(event("{}", "factoryops.missing.v1")))
          .isInstanceOf(Exception.class);
    } finally {
      template.destroy();
    }
  }

  private KafkaTemplate<String, byte[]> template() {
    var producerProperties =
        Map.<String, Object>of(
            ProducerConfig.BOOTSTRAP_SERVERS_CONFIG,
            KAFKA.getBootstrapServers(),
            ProducerConfig.ACKS_CONFIG,
            "all",
            ProducerConfig.ENABLE_IDEMPOTENCE_CONFIG,
            true,
            ProducerConfig.REQUEST_TIMEOUT_MS_CONFIG,
            5_000,
            ProducerConfig.DELIVERY_TIMEOUT_MS_CONFIG,
            10_000,
            ProducerConfig.KEY_SERIALIZER_CLASS_CONFIG,
            StringSerializer.class,
            ProducerConfig.VALUE_SERIALIZER_CLASS_CONFIG,
            ByteArraySerializer.class);
    return new KafkaTemplate<>(new DefaultKafkaProducerFactory<String, byte[]>(producerProperties));
  }

  private KafkaConsumer<String, byte[]> consumer() {
    var properties = new Properties();
    properties.put(ConsumerConfig.BOOTSTRAP_SERVERS_CONFIG, KAFKA.getBootstrapServers());
    properties.put(ConsumerConfig.GROUP_ID_CONFIG, "publisher-it");
    properties.put(ConsumerConfig.AUTO_OFFSET_RESET_CONFIG, "earliest");
    properties.put(ConsumerConfig.KEY_DESERIALIZER_CLASS_CONFIG, StringDeserializer.class);
    properties.put(ConsumerConfig.VALUE_DESERIALIZER_CLASS_CONFIG, ByteArrayDeserializer.class);
    return new KafkaConsumer<>(properties);
  }

  private OutboxEvent event(String payload) {
    return event(payload, TOPIC);
  }

  private OutboxEvent event(String payload, String topic) {
    return new OutboxEvent(
        "EVT-1",
        "quality-incident",
        "QI-1",
        "quality.incident.opened",
        "1.0",
        topic,
        "QI-1",
        Instant.EPOCH,
        payload,
        "PENDING",
        0,
        Instant.EPOCH,
        null,
        null,
        Instant.EPOCH);
  }
}
