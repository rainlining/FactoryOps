package com.factoryops.business.incident.infrastructure;

import com.factoryops.business.incident.domain.QualityIncident;
import com.factoryops.business.inspection.infrastructure.InspectionJdbcRepository;
import java.util.Optional;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.stereotype.Repository;

@Repository
public class QualityIncidentJdbcRepository {
  private final JdbcTemplate jdbc;

  public QualityIncidentJdbcRepository(JdbcTemplate jdbc) {
    this.jdbc = jdbc;
  }

  public void insert(QualityIncident incident) {
    jdbc.update(
        """
        INSERT INTO quality_incidents (
          incident_id_hash, incident_id, incident_schema_version, status,
          batch_id_hash, batch_id, inspection_id_hash, inspection_id,
          result_id_hash, result_id, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        InspectionJdbcRepository.hash(incident.id()), incident.id(), incident.schemaVersion(),
        incident.status(), InspectionJdbcRepository.hash(incident.batchId()), incident.batchId(),
        InspectionJdbcRepository.hash(incident.inspectionId()), incident.inspectionId(),
        InspectionJdbcRepository.hash(incident.resultId()), incident.resultId(), incident.createdAt());
  }

  public Optional<QualityIncident> findById(String id) {
    return query("incident_id_hash", "incident_id", id);
  }

  public Optional<QualityIncident> findByResultId(String resultId) {
    return query("result_id_hash", "result_id", resultId);
  }

  private Optional<QualityIncident> query(String hashColumn, String idColumn, String value) {
    return jdbc.query(
        "SELECT incident_id, incident_schema_version, status, batch_id, inspection_id, result_id, created_at "
            + "FROM quality_incidents WHERE " + hashColumn + " = ? AND " + idColumn + " = ?",
        (rs, row) -> new QualityIncident(rs.getString(1), rs.getString(2), rs.getString(3),
            rs.getString(4), rs.getString(5), rs.getString(6), rs.getTimestamp(7).toInstant()),
        InspectionJdbcRepository.hash(value), value).stream().findFirst();
  }
}
