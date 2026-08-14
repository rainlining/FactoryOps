package com.factoryops.business.outbox.application;

import com.factoryops.business.incident.domain.QualityIncident;
import com.factoryops.business.inspection.application.CanonicalJson;
import com.factoryops.business.outbox.domain.OutboxEvent;
import java.nio.charset.StandardCharsets;
import java.security.MessageDigest;
import java.security.NoSuchAlgorithmException;
import java.time.Instant;
import java.time.ZoneOffset;
import java.time.format.DateTimeFormatter;
import java.time.temporal.ChronoUnit;
import java.util.HexFormat;
import org.springframework.stereotype.Component;
import tools.jackson.databind.json.JsonMapper;

@Component
public final class QualityIncidentOpenedEventFactory {
  private static final String EVENT_NAMESPACE =
      "factoryops:event:quality.incident.opened:v1:";
  private static final String EVENT_TYPE = "quality.incident.opened";
  private static final String TOPIC = "factoryops.quality.incident.v1";
  private static final DateTimeFormatter UTC_MICROS =
      DateTimeFormatter.ofPattern("uuuu-MM-dd'T'HH:mm:ss.SSSSSS'Z'")
          .withZone(ZoneOffset.UTC);

  private final JsonMapper mapper;

  public QualityIncidentOpenedEventFactory(JsonMapper mapper) {
    this.mapper = mapper;
  }

  public OutboxEvent create(QualityIncident incident, Instant outboxCreatedAt) {
    var eventId = deriveEventId(incident.id());
    var envelope = mapper.createObjectNode();
    envelope.put("contract_version", "1.0");
    envelope.put("event_id", eventId);
    envelope.put("event_type", EVENT_TYPE);
    envelope.put("occurred_at", format(incident.createdAt()));

    envelope.set(
        "producer",
        mapper
            .createObjectNode()
            .put("name", "factoryops-business-service")
            .put("version", "0.1.0"));
    envelope.set(
        "aggregate",
        mapper.createObjectNode().put("type", "quality-incident").put("id", incident.id()));
    envelope.put("correlation_id", incident.id());
    envelope.put("causation_id", incident.resultId());
    envelope.set(
        "payload",
        mapper
            .createObjectNode()
            .put("incident_schema_version", incident.schemaVersion())
            .put("incident_id", incident.id())
            .put("status", incident.status())
            .put("batch_id", incident.batchId())
            .put("inspection_id", incident.inspectionId())
            .put("result_id", incident.resultId()));

    var canonical =
        new String(CanonicalJson.canonicalize(envelope), StandardCharsets.UTF_8);
    var createdAt = outboxCreatedAt.truncatedTo(ChronoUnit.MICROS);
    return new OutboxEvent(
        eventId,
        "quality-incident",
        incident.id(),
        EVENT_TYPE,
        "1.0",
        TOPIC,
        incident.id(),
        incident.createdAt(),
        canonical,
        "PENDING",
        0,
        createdAt,
        null,
        null,
        createdAt);
  }

  public static String deriveEventId(String incidentId) {
    try {
      var digest =
          MessageDigest.getInstance("SHA-256")
              .digest((EVENT_NAMESPACE + incidentId).getBytes(StandardCharsets.UTF_8));
      return "EVT-" + HexFormat.of().withUpperCase().formatHex(digest);
    } catch (NoSuchAlgorithmException impossible) {
      throw new IllegalStateException("JVM does not provide SHA-256", impossible);
    }
  }

  private static String format(Instant value) {
    return UTC_MICROS.format(value.truncatedTo(ChronoUnit.MICROS));
  }
}
