package com.factoryops.business.outbox.application;

import static org.assertj.core.api.Assertions.assertThat;

import com.factoryops.business.incident.domain.QualityIncident;
import com.networknt.schema.SchemaRegistry;
import com.networknt.schema.SpecificationVersion;
import java.time.Instant;
import org.junit.jupiter.api.Test;
import tools.jackson.databind.json.JsonMapper;

class QualityIncidentOpenedEventFactoryTest {
  private final JsonMapper mapper = JsonMapper.builder().build();
  private final QualityIncidentOpenedEventFactory factory =
      new QualityIncidentOpenedEventFactory(mapper);

  @Test
  void creates_stable_pending_event_that_matches_shared_contract() throws Exception {
    var incident =
        QualityIncident.open(
            "B-17",
            "inspection-00731",
            "result-1",
            Instant.parse("2026-08-14T01:02:03.123456Z"));
    var event = factory.create(incident, Instant.parse("2026-08-14T02:00:00Z"));

    assertThat(event.eventId())
        .isEqualTo("EVT-CB0CF1FDEF58FAE6DE62ADC2AB52EBDBFF2405EC4302E078D7587870C2A2FC75");
    assertThat(event.aggregateId()).isEqualTo(incident.id());
    assertThat(event.topic()).isEqualTo("factoryops.quality.incident.v1");
    assertThat(event.messageKey()).isEqualTo(incident.id());
    assertThat(event.occurredAt()).isEqualTo(incident.createdAt());
    assertThat(event.createdAt()).isEqualTo(Instant.parse("2026-08-14T02:00:00Z"));
    assertThat(event.availableAt()).isEqualTo(event.createdAt());
    assertThat(event.status()).isEqualTo("PENDING");
    assertThat(event.attemptCount()).isZero();
    assertThat(event.publishedAt()).isNull();
    assertThat(event.lastError()).isNull();

    var payload = mapper.readTree(event.payload());
    assertThat(payload.get("occurred_at").asText()).isEqualTo("2026-08-14T01:02:03.123456Z");
    assertThat(payload.get("payload").has("anomaly_score")).isFalse();
    try (var input = getClass().getResourceAsStream(
        "/contracts/quality_incident_opened/v1.0/schema.json")) {
      assertThat(input).isNotNull();
      var schema =
          SchemaRegistry.withDefaultDialect(SpecificationVersion.DRAFT_2020_12)
              .getSchema(mapper.readTree(input));
      assertThat(schema.validate(payload)).isEmpty();
    }
  }

  @Test
  void canonical_payload_is_independent_of_outbox_write_time() {
    var incident = QualityIncident.open("B-1", "I-1", "result-1", Instant.EPOCH);

    var first = factory.create(incident, Instant.parse("2026-08-14T02:00:00Z"));
    var replay = factory.create(incident, Instant.parse("2026-08-15T02:00:00Z"));

    assertThat(replay.eventId()).isEqualTo(first.eventId());
    assertThat(replay.payload()).isEqualTo(first.payload());
  }
}
