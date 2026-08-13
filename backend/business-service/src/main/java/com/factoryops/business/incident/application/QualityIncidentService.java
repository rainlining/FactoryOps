package com.factoryops.business.incident.application;

import com.factoryops.business.incident.domain.QualityIncident;
import com.factoryops.business.incident.infrastructure.QualityIncidentJdbcRepository;
import com.factoryops.business.inspection.application.ValidatedVisionResult;
import com.factoryops.business.inspection.domain.Inspection;
import java.time.Instant;
import org.springframework.stereotype.Service;

@Service
public class QualityIncidentService {
  private final QualityIncidentJdbcRepository incidents;

  public QualityIncidentService(QualityIncidentJdbcRepository incidents) {
    this.incidents = incidents;
  }

  public String openOrFind(Inspection inspection, ValidatedVisionResult result, Instant createdAt) {
    if (!result.anomaly()) {
      return null;
    }
    var existing = incidents.findByResultId(result.resultId());
    if (existing.isPresent()) {
      return existing.get().id();
    }
    var incident = QualityIncident.open(
        inspection.batchId(), inspection.id(), result.resultId(), createdAt);
    incidents.insert(incident);
    return incident.id();
  }

  public String findForReplay(ValidatedVisionResult result) {
    if (!result.anomaly()) {
      return null;
    }
    return incidents.findByResultId(result.resultId())
        .orElseThrow(() -> new IllegalStateException("anomaly result has no incident"))
        .id();
  }
}
