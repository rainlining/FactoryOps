package com.factoryops.business.inspection.infrastructure;

import com.factoryops.business.inspection.domain.*;
import java.nio.charset.StandardCharsets;
import java.security.MessageDigest;
import java.time.Instant;
import java.util.Optional;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.stereotype.Repository;

@Repository
public class InspectionJdbcRepository {
  private final JdbcTemplate jdbc;

  public InspectionJdbcRepository(JdbcTemplate jdbc) {
    this.jdbc = jdbc;
  }

  public void insert(Inspection i) {
    jdbc.update(
        "INSERT INTO inspections"
            + " (inspection_id_hash,inspection_id,expected_image_uri,expected_image_sha256,status,created_at,completed_at,batch_id_hash,batch_id)"
            + " VALUES (?,?,?,?,?,?,?,?,?)",
        hash(i.id()),
        i.id(),
        i.input().imageUri(),
        i.input().sha256(),
        i.status().name(),
        i.createdAt(),
        i.completedAt(),
        hash(i.batchId()),
        i.batchId());
  }

  public Optional<Inspection> find(String id) {
    return jdbc
        .query(
            "SELECT"
                + " inspection_id,batch_id,expected_image_uri,expected_image_sha256,status,created_at,completed_at"
                + " FROM inspections WHERE inspection_id_hash=?",
            (rs, n) ->
                Inspection.restore(
                    rs.getString(1),
                    rs.getString(2),
                    new InspectionInput(rs.getString(3), rs.getString(4)),
                    InspectionStatus.valueOf(rs.getString(5)),
                    rs.getTimestamp(6).toInstant(),
                    rs.getTimestamp(7) == null ? null : rs.getTimestamp(7).toInstant()),
            hash(id))
        .stream()
        .filter(i -> i.id().equals(id))
        .findFirst();
  }

  public int completePending(String id, Instant at) {
    return jdbc.update(
        "UPDATE inspections SET status='COMPLETED', completed_at=? WHERE inspection_id_hash=? AND"
            + " inspection_id=? AND status='PENDING'",
        at,
        hash(id),
        id);
  }

  public static byte[] hash(String value) {
    try {
      return MessageDigest.getInstance("SHA-256").digest(value.getBytes(StandardCharsets.UTF_8));
    } catch (Exception impossible) {
      throw new IllegalStateException(impossible);
    }
  }
}
