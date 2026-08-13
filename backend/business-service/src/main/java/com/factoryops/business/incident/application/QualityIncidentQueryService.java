package com.factoryops.business.incident.application;

import com.factoryops.business.incident.domain.QualityIncident;
import com.factoryops.business.incident.infrastructure.QualityIncidentJdbcRepository;
import org.springframework.beans.factory.annotation.Qualifier;
import org.springframework.stereotype.Service;
import org.springframework.transaction.support.TransactionTemplate;

@Service
public class QualityIncidentQueryService {
  private final QualityIncidentJdbcRepository incidents;
  private final TransactionTemplate readTransaction;

  public QualityIncidentQueryService(
      QualityIncidentJdbcRepository incidents,
      @Qualifier("inspectionReadTransaction") TransactionTemplate readTransaction) {
    this.incidents = incidents;
    this.readTransaction = readTransaction;
  }

  public QualityIncident get(String id) {
    return readTransaction.execute(status -> incidents.findById(id)
        .orElseThrow(QualityIncidentNotFoundException::new));
  }
}
