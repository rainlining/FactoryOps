package com.factoryops.business.incident.application;

import com.factoryops.business.incident.domain.QualityIncident;
import com.factoryops.business.incident.infrastructure.QualityIncidentJdbcRepository;
import com.factoryops.business.inspection.infrastructure.InspectionResultJdbcRepository;
import org.springframework.beans.factory.annotation.Qualifier;
import org.springframework.stereotype.Service;
import org.springframework.transaction.support.TransactionTemplate;

@Service
public class QualityIncidentQueryService {
  private final QualityIncidentJdbcRepository incidents;
  private final InspectionResultJdbcRepository results;
  private final TransactionTemplate readTransaction;

  public QualityIncidentQueryService(
      QualityIncidentJdbcRepository incidents,
      InspectionResultJdbcRepository results,
      @Qualifier("inspectionReadTransaction") TransactionTemplate readTransaction) {
    this.incidents = incidents;
    this.results = results;
    this.readTransaction = readTransaction;
  }

  public QualityIncidentView get(String id) {
    return readTransaction.execute(
        status -> {
          var incident =
              incidents.findById(id).orElseThrow(QualityIncidentNotFoundException::new);
          var originKind =
              results
                  .findOriginKindByResultId(incident.resultId())
                  .orElseThrow(
                      () ->
                          new IllegalStateException(
                              "quality incident references a missing inspection result"));
          return new QualityIncidentView(incident, originKind);
        });
  }

  public record QualityIncidentView(QualityIncident incident, String resultOriginKind) {}
}
