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
    public InspectionJdbcRepository(JdbcTemplate jdbc) { this.jdbc = jdbc; }

    public void insert(Inspection i) {
        jdbc.update("INSERT INTO inspections VALUES (?, ?, ?, ?, ?, ?, ?)", hash(i.id()), i.id(), i.input().imageUri(), i.input().sha256(), i.status().name(), i.createdAt(), i.completedAt());
    }
    public Optional<Inspection> find(String id) {
        return jdbc.query("SELECT inspection_id,expected_image_uri,expected_image_sha256,status,created_at,completed_at FROM inspections WHERE inspection_id_hash=?",
                (rs,n) -> Inspection.restore(rs.getString(1), new InspectionInput(rs.getString(2),rs.getString(3)), InspectionStatus.valueOf(rs.getString(4)), rs.getTimestamp(5).toInstant(), rs.getTimestamp(6)==null?null:rs.getTimestamp(6).toInstant()), hash(id))
                .stream().filter(i -> i.id().equals(id)).findFirst();
    }
    public int completePending(String id, Instant at) {
        return jdbc.update("UPDATE inspections SET status='COMPLETED', completed_at=? WHERE inspection_id_hash=? AND inspection_id=? AND status='PENDING'", at, hash(id), id);
    }
    public static byte[] hash(String value) {
        try { return MessageDigest.getInstance("SHA-256").digest(value.getBytes(StandardCharsets.UTF_8)); }
        catch (Exception impossible) { throw new IllegalStateException(impossible); }
    }
}
