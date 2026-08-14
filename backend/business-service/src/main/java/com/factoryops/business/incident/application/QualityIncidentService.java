package com.factoryops.business.incident.application;

import com.factoryops.business.incident.domain.QualityIncident;
import com.factoryops.business.incident.infrastructure.QualityIncidentJdbcRepository;
import com.factoryops.business.inspection.application.ValidatedVisionResult;
import com.factoryops.business.inspection.domain.Inspection;
import com.factoryops.business.outbox.application.QualityIncidentOpenedEventFactory;
import com.factoryops.business.outbox.infrastructure.OutboxEventJdbcRepository;
import java.time.Instant;
import org.springframework.stereotype.Service;

@Service
public class QualityIncidentService {
  private final QualityIncidentJdbcRepository incidents;
  private final QualityIncidentOpenedEventFactory eventFactory;
  private final OutboxEventJdbcRepository outbox;

  public QualityIncidentService(
      QualityIncidentJdbcRepository incidents,
      QualityIncidentOpenedEventFactory eventFactory,
      OutboxEventJdbcRepository outbox) {
    this.incidents = incidents;
    this.eventFactory = eventFactory;
    this.outbox = outbox;
  }

  public String openOrFind(Inspection inspection, ValidatedVisionResult result, Instant createdAt) {
    if (!result.anomaly()) {
      return null;
    }
    var existing = incidents.findByResultId(result.resultId());
    if (existing.isPresent()) {
      var incident = existing.get();
      outbox.requireMatching(eventFactory.create(incident, incident.createdAt()));
      return incident.id();
    }
    var incident =
        QualityIncident.open(inspection.batchId(), inspection.id(), result.resultId(), createdAt);
    incidents.insert(incident);
    outbox.insert(eventFactory.create(incident, createdAt));
    return incident.id();
  }

  public String findForReplay(ValidatedVisionResult result) {
    if (!result.anomaly()) {
      return null;
    }
    var incident =
        incidents
            .findByResultId(result.resultId())
            .orElseThrow(() -> new IllegalStateException("anomaly result has no incident"));
    outbox.requireMatching(eventFactory.create(incident, incident.createdAt()));
    return incident.id();
  }
}
