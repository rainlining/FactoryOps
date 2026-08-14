package com.factoryops.business.incident.domain;

import java.time.Instant;
import java.time.temporal.ChronoUnit;
import java.util.Objects;

public record QualityIncident(
    String id,
    String schemaVersion,
    String status,
    String batchId,
    String inspectionId,
    String resultId,
    Instant createdAt) {

  public QualityIncident {
    QualityIncidentId.requireText(id, "incident_id");
    QualityIncidentId.requireText(batchId, "batch_id");
    QualityIncidentId.requireText(inspectionId, "inspection_id");
    QualityIncidentId.requireText(resultId, "result_id");
    if (!"1.0".equals(schemaVersion) || !"OPEN".equals(status)) {
      throw new IllegalArgumentException("unsupported incident version or status");
    }
    Objects.requireNonNull(createdAt, "created_at");
  }

  public static QualityIncident open(
      String batchId, String inspectionId, String resultId, Instant createdAt) {
    return new QualityIncident(
        QualityIncidentId.fromResultId(resultId),
        "1.0",
        "OPEN",
        batchId,
        inspectionId,
        resultId,
        createdAt.truncatedTo(ChronoUnit.MICROS));
  }
}
