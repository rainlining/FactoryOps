package com.factoryops.business.outbox.infrastructure;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;

import com.factoryops.business.outbox.publisher.OutboxPublicationStateException;
import java.sql.DriverManager;
import org.flywaydb.core.Flyway;
import org.junit.jupiter.api.BeforeAll;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.jdbc.datasource.SingleConnectionDataSource;
import org.testcontainers.junit.jupiter.Container;
import org.testcontainers.junit.jupiter.Testcontainers;
import org.testcontainers.mysql.MySQLContainer;

@Testcontainers
class OutboxPublisherRepositoryIT {
  private static final String EVENT_A = "EVT-" + "0".repeat(63) + "A";
  private static final String EVENT_B = "EVT-" + "0".repeat(63) + "B";
  private static final String EVENT_FUTURE = "EVT-" + "0".repeat(63) + "C";
  private static final String EVENT_PUBLISHED = "EVT-" + "0".repeat(63) + "D";

  @Container static final MySQLContainer MYSQL = new MySQLContainer("mysql:8.4");

  private static JdbcTemplate jdbc;
  private static OutboxEventJdbcRepository repository;

  @BeforeAll
  static void migrateAndSeed() throws Exception {
    Flyway.configure()
        .dataSource(MYSQL.getJdbcUrl(), MYSQL.getUsername(), MYSQL.getPassword())
        .load()
        .migrate();
    var connection =
        DriverManager.getConnection(MYSQL.getJdbcUrl(), MYSQL.getUsername(), MYSQL.getPassword());
    jdbc = new JdbcTemplate(new SingleConnectionDataSource(connection, true));
    repository = new OutboxEventJdbcRepository(jdbc);
    jdbc.execute("SET FOREIGN_KEY_CHECKS=0");
    insert(EVENT_B, "2026-08-14 00:00:00.000002", "PENDING", null);
    insert(EVENT_A, "2026-08-14 00:00:00.000001", "PENDING", null);
    insert(EVENT_FUTURE, "2037-08-14 00:00:00.000000", "PENDING", null);
    insert(
        EVENT_PUBLISHED, "2026-08-14 00:00:00.000000", "PUBLISHED", "2026-08-14 01:00:00.000000");
  }

  @BeforeEach
  void resetMutableFixture() {
    jdbc.update(
        "UPDATE outbox_events SET status='PENDING', published_at=NULL WHERE event_id=?", EVENT_A);
  }

  @Test
  void selects_only_due_pending_rows_in_stable_order_with_limit() {
    assertThat(repository.findPublishable(1))
        .extracting(event -> event.eventId())
        .containsExactly(EVENT_A);
    assertThat(repository.findPublishable(10))
        .extracting(event -> event.eventId())
        .containsExactly(EVENT_A, EVENT_B);
  }

  @Test
  void conditionally_marks_pending_row_published_once() {
    var publishedAt = repository.markPublished(EVENT_A);

    assertThat(publishedAt).isNotNull();
    assertThat(repository.findByEventId(EVENT_A).orElseThrow().status()).isEqualTo("PUBLISHED");
    assertThatThrownBy(() -> repository.markPublished(EVENT_A))
        .isInstanceOf(OutboxPublicationStateException.class);
  }

  private static void insert(
      String eventId, String availableAt, String status, String publishedAt) {
    jdbc.update(
        """
        INSERT INTO outbox_events (
          event_id, aggregate_type, aggregate_id_hash, aggregate_id, event_type,
          contract_version, topic, message_key, occurred_at, payload, status,
          attempt_count, available_at, published_at, last_error, created_at)
        VALUES (?, 'quality-incident', UNHEX(SHA2(?,256)), ?, 'quality.incident.opened',
          '1.0', 'factoryops.quality.incident.v1', ?, '2026-08-14 00:00:00.000000',
          '{}', ?, 0, ?, ?, NULL, ?)
        """,
        eventId,
        eventId,
        "QI-" + eventId.substring(4),
        "QI-" + eventId.substring(4),
        status,
        availableAt,
        publishedAt,
        availableAt);
  }
}
