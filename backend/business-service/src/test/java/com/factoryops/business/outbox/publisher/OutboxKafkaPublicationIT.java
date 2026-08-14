package com.factoryops.business.outbox.publisher;

import static java.nio.charset.StandardCharsets.UTF_8;
import static org.assertj.core.api.Assertions.assertThat;

import com.factoryops.business.outbox.infrastructure.OutboxEventJdbcRepository;
import java.sql.DriverManager;
import java.time.Duration;
import java.util.List;
import java.util.Map;
import java.util.Properties;
import java.util.stream.StreamSupport;
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
import org.flywaydb.core.Flyway;
import org.junit.jupiter.api.BeforeAll;
import org.junit.jupiter.api.Test;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.jdbc.datasource.SingleConnectionDataSource;
import org.springframework.kafka.core.DefaultKafkaProducerFactory;
import org.springframework.kafka.core.KafkaTemplate;
import org.testcontainers.junit.jupiter.Container;
import org.testcontainers.junit.jupiter.Testcontainers;
import org.testcontainers.kafka.KafkaContainer;
import org.testcontainers.mysql.MySQLContainer;

@Testcontainers
class OutboxKafkaPublicationIT {
  private static final String TOPIC = "factoryops.quality.incident.v1";
  private static final String EVENT_ID = "EVT-" + "1".repeat(64);
  private static final String MESSAGE_KEY = "QI-" + "2".repeat(64);
  private static final String PAYLOAD = "{\"incident_id\":\"QI-重复发布实验\"}";

  @Container static final MySQLContainer MYSQL = new MySQLContainer("mysql:8.4");

  @Container
  static final KafkaContainer KAFKA =
      new KafkaContainer("apache/kafka-native:4.1.0")
          .withEnv("KAFKA_AUTO_CREATE_TOPICS_ENABLE", "false");

  private static JdbcTemplate jdbc;
  private static OutboxEventJdbcRepository repository;

  @BeforeAll
  static void prepareInfrastructure() throws Exception {
    Flyway.configure()
        .dataSource(MYSQL.getJdbcUrl(), MYSQL.getUsername(), MYSQL.getPassword())
        .load()
        .migrate();
    var connection =
        DriverManager.getConnection(MYSQL.getJdbcUrl(), MYSQL.getUsername(), MYSQL.getPassword());
    jdbc = new JdbcTemplate(new SingleConnectionDataSource(connection, true));
    repository = new OutboxEventJdbcRepository(jdbc);
    jdbc.execute("SET FOREIGN_KEY_CHECKS=0");
    insertPendingEvent();

    try (var admin =
        AdminClient.create(
            Map.of(AdminClientConfig.BOOTSTRAP_SERVERS_CONFIG, KAFKA.getBootstrapServers()))) {
      admin.createTopics(List.of(new NewTopic(TOPIC, 3, (short) 1))).all().get();
    }
  }

  @Test
  void republishes_same_event_when_kafka_ack_succeeds_but_database_mark_fails() {
    var template = template();
    var properties = new OutboxPublisherProperties();
    properties.setDeliveryTimeout(Duration.ofSeconds(10));
    var sender = new KafkaOutboxEventSender(template, properties);
    var failFirstMark = new FailFirstMarkRepository(repository);

    try (var consumer = consumer()) {
      consumer.subscribe(List.of(TOPIC));

      var firstSummary =
          new OutboxPublicationService(sender, failFirstMark)
              .publish(repository.findPublishable(50));
      assertThat(firstSummary.failed()).isEqualTo(1);
      assertThat(repository.findByEventId(EVENT_ID).orElseThrow().status()).isEqualTo("PENDING");

      var secondSummary =
          new OutboxPublicationService(sender, repository).publish(repository.findPublishable(50));
      assertThat(secondSummary.published()).isEqualTo(1);
      assertThat(repository.findByEventId(EVENT_ID).orElseThrow().status()).isEqualTo("PUBLISHED");

      var records =
          StreamSupport.stream(
                  consumer.poll(Duration.ofSeconds(10)).records(TOPIC).spliterator(), false)
              .toList();
      assertThat(records).hasSize(2);
      assertThat(records)
          .allSatisfy(
              record -> {
                assertThat(record.key()).isEqualTo(MESSAGE_KEY);
                assertThat(record.value()).isEqualTo(PAYLOAD.getBytes(UTF_8));
              });
      assertThat(records.get(0).offset()).isNotEqualTo(records.get(1).offset());
    } finally {
      template.destroy();
    }
  }

  private static void insertPendingEvent() {
    jdbc.update(
        """
        INSERT INTO outbox_events (
          event_id, aggregate_type, aggregate_id_hash, aggregate_id, event_type,
          contract_version, topic, message_key, occurred_at, payload, status,
          attempt_count, available_at, published_at, last_error, created_at)
        VALUES (?, 'quality-incident', UNHEX(SHA2(?,256)), ?, 'quality.incident.opened',
          '1.0', ?, ?, CURRENT_TIMESTAMP(6), ?, 'PENDING', 0,
          CURRENT_TIMESTAMP(6), NULL, NULL, CURRENT_TIMESTAMP(6))
        """,
        EVENT_ID,
        MESSAGE_KEY,
        MESSAGE_KEY,
        TOPIC,
        MESSAGE_KEY,
        PAYLOAD);
  }

  private static KafkaTemplate<String, byte[]> template() {
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

  private static KafkaConsumer<String, byte[]> consumer() {
    var properties = new Properties();
    properties.put(ConsumerConfig.BOOTSTRAP_SERVERS_CONFIG, KAFKA.getBootstrapServers());
    properties.put(ConsumerConfig.GROUP_ID_CONFIG, "outbox-at-least-once-it");
    properties.put(ConsumerConfig.AUTO_OFFSET_RESET_CONFIG, "earliest");
    properties.put(ConsumerConfig.KEY_DESERIALIZER_CLASS_CONFIG, StringDeserializer.class);
    properties.put(ConsumerConfig.VALUE_DESERIALIZER_CLASS_CONFIG, ByteArrayDeserializer.class);
    return new KafkaConsumer<>(properties);
  }

  private static final class FailFirstMarkRepository implements OutboxPublicationRepository {
    private final OutboxPublicationRepository delegate;
    private boolean first = true;

    private FailFirstMarkRepository(OutboxPublicationRepository delegate) {
      this.delegate = delegate;
    }

    @Override
    public List<com.factoryops.business.outbox.domain.OutboxEvent> findPublishable(int limit) {
      return delegate.findPublishable(limit);
    }

    @Override
    public java.time.Instant markPublished(String eventId) {
      if (first) {
        first = false;
        throw new IllegalStateException("injected database mark failure");
      }
      return delegate.markPublished(eventId);
    }
  }
}
