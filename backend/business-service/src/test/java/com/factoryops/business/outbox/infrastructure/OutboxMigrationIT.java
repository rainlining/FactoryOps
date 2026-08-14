package com.factoryops.business.outbox.infrastructure;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;

import com.factoryops.business.incident.domain.QualityIncident;
import com.factoryops.business.outbox.application.OutboxIntegrityException;
import com.factoryops.business.outbox.application.QualityIncidentOpenedEventFactory;
import com.factoryops.business.outbox.domain.OutboxEvent;
import java.nio.charset.StandardCharsets;
import java.sql.DriverManager;
import java.time.Instant;
import java.util.Calendar;
import java.util.TimeZone;
import org.flywaydb.core.Flyway;
import org.junit.jupiter.api.Test;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.jdbc.datasource.DriverManagerDataSource;
import org.testcontainers.junit.jupiter.Container;
import org.testcontainers.junit.jupiter.Testcontainers;
import org.testcontainers.mysql.MySQLContainer;
import tools.jackson.databind.json.JsonMapper;

@Testcontainers
class OutboxMigrationIT {
  @Container static final MySQLContainer MYSQL = new MySQLContainer("mysql:8.4");

  @Test
  void v5_backfills_each_historical_open_incident_with_contract_event() throws Exception {
    var v1 = flyway("1");
    v1.clean();
    v1.migrate();
    var resultPayload = fixture("/fixtures/valid/vision-service-result.json");
    try (var connection = connection();
        var statement =
            connection.prepareStatement(
                """
                INSERT INTO vision_inspection_results (
                  result_id_hash, result_id, inspection_id_hash, inspection_id,
                  origin_kind, anomaly_score_text, decision_threshold_text,
                  canonical_payload, payload_hash, created_at)
                VALUES (
                  UNHEX(SHA2('result-1001',256)), 'result-1001',
                  UNHEX(SHA2('inspection-00731',256)), 'inspection-00731',
                  'vision-service', '0.72', '0.60', ?, UNHEX(SHA2(?,256)), ?)
                """)) {
      statement.setString(1, resultPayload);
      statement.setString(2, resultPayload);
      statement.setTimestamp(
          3,
          java.sql.Timestamp.from(Instant.parse("2026-08-14T01:02:03.123456Z")),
          Calendar.getInstance(TimeZone.getTimeZone("UTC")));
      statement.executeUpdate();
    }

    flyway("5").migrate();

    try (var connection = connection();
        var statement = connection.createStatement();
        var row =
            statement.executeQuery(
                """
                SELECT event_id, aggregate_id, occurred_at, payload, status,
                       attempt_count, published_at, last_error
                FROM outbox_events
                """)) {
      assertThat(row.next()).isTrue();
      var incidentId = "QI-B189C85A634933C66A6B084D07C3D5BFAC1D031176968F2C2067C4E3657C9E49";
      assertThat(row.getString("event_id"))
          .isEqualTo("EVT-9792A34B246A62F3EC748095244C8CF2790AB951B48D1EBCF144CEE73ACCAAEA");
      assertThat(row.getString("aggregate_id")).isEqualTo(incidentId);
      assertThat(row.getTimestamp("occurred_at").toInstant())
          .isEqualTo(Instant.parse("2026-08-14T01:02:03.123456Z"));
      assertThat(row.getString("status")).isEqualTo("PENDING");
      assertThat(row.getInt("attempt_count")).isZero();
      assertThat(row.getTimestamp("published_at")).isNull();
      assertThat(row.getString("last_error")).isNull();

      var expected =
          new QualityIncidentOpenedEventFactory(JsonMapper.builder().build())
              .create(
                  new QualityIncident(
                      incidentId,
                      "1.0",
                      "OPEN",
                      "SYS-LEGACY-UNASSIGNED",
                      "inspection-00731",
                      "result-1001",
                      Instant.parse("2026-08-14T01:02:03.123456Z")),
                  Instant.EPOCH)
              .payload();
      assertThat(row.getString("payload")).isEqualTo(expected);
      assertThat(row.next()).isFalse();
    }

    var repository = repository();
    var incident =
        new QualityIncident(
            "QI-B189C85A634933C66A6B084D07C3D5BFAC1D031176968F2C2067C4E3657C9E49",
            "1.0",
            "OPEN",
            "SYS-LEGACY-UNASSIGNED",
            "inspection-00731",
            "result-1001",
            Instant.parse("2026-08-14T01:02:03.123456Z"));
    var expected =
        new QualityIncidentOpenedEventFactory(JsonMapper.builder().build())
            .create(incident, Instant.EPOCH);
    assertThat(repository.findByEventId(expected.eventId())).isPresent();
    repository.requireMatching(expected);

    var conflicting =
        new OutboxEvent(
            expected.eventId(),
            expected.aggregateType(),
            expected.aggregateId(),
            expected.eventType(),
            expected.contractVersion(),
            "factoryops.wrong.topic",
            expected.messageKey(),
            expected.occurredAt(),
            expected.payload(),
            expected.status(),
            expected.attemptCount(),
            expected.availableAt(),
            expected.publishedAt(),
            expected.lastError(),
            expected.createdAt());
    assertThatThrownBy(() -> repository.requireMatching(conflicting))
        .isInstanceOf(OutboxIntegrityException.class);
  }

  private Flyway flyway(String target) {
    return Flyway.configure()
        .dataSource(jdbcUrl(), MYSQL.getUsername(), MYSQL.getPassword())
        .cleanDisabled(false)
        .target(target)
        .load();
  }

  private java.sql.Connection connection() throws Exception {
    return DriverManager.getConnection(jdbcUrl(), MYSQL.getUsername(), MYSQL.getPassword());
  }

  private OutboxEventJdbcRepository repository() {
    var dataSource =
        new DriverManagerDataSource(jdbcUrl(), MYSQL.getUsername(), MYSQL.getPassword());
    return new OutboxEventJdbcRepository(new JdbcTemplate(dataSource));
  }

  private String jdbcUrl() {
    return MYSQL.getJdbcUrl() + "?connectionTimeZone=UTC&forceConnectionTimeZoneToSession=true";
  }

  private String fixture(String name) throws Exception {
    try (var input = getClass().getResourceAsStream(name)) {
      return new String(input.readAllBytes(), StandardCharsets.UTF_8);
    }
  }
}
