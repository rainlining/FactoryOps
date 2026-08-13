package com.factoryops.business.inspection.infrastructure;

import com.factoryops.business.inspection.application.ValidatedVisionResult;
import java.nio.charset.StandardCharsets;
import java.security.MessageDigest;
import java.security.NoSuchAlgorithmException;
import java.util.Optional;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.stereotype.Repository;

@Repository
public class InspectionResultJdbcRepository {
    private final JdbcTemplate jdbc;

    public InspectionResultJdbcRepository(JdbcTemplate jdbc) {
        this.jdbc = jdbc;
    }

    public void insert(ValidatedVisionResult result) {
        jdbc.update("""
                INSERT INTO vision_inspection_results
                  (result_id_hash, result_id, inspection_id_hash, inspection_id, origin_kind,
                   anomaly_score_text, decision_threshold_text, canonical_payload, payload_hash)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                hash(result.resultId()), result.resultId(), hash(result.inspectionId()), result.inspectionId(),
                result.originKind(), normalize(result.anomalyScore()), normalize(result.decisionThreshold()),
                new String(result.canonicalPayload(), StandardCharsets.UTF_8), result.payloadHash());
    }

    public Optional<StoredInspectionResult> findByResultId(String resultId) {
        var rows = jdbc.query("""
                SELECT result_id, payload_hash FROM vision_inspection_results WHERE result_id_hash = ?
                """, (rs, row) -> new StoredInspectionResult(rs.getString(1), rs.getBytes(2)), hash(resultId));
        return rows.stream().filter(row -> row.resultId().equals(resultId)).findFirst();
    }
    public Optional<ResultEvidence> findEvidence(String resultId){return jdbc.query("SELECT result_id,inspection_id,JSON_EXTRACT(canonical_payload,'$.observation.is_anomaly') FROM vision_inspection_results WHERE result_id_hash=?",(rs,n)->new ResultEvidence(rs.getString(1),rs.getString(2),rs.getBoolean(3)),hash(resultId)).stream().filter(r->r.resultId().equals(resultId)).findFirst();}
    public record ResultEvidence(String resultId,String inspectionId,boolean anomaly){}

    private static String normalize(java.math.BigDecimal value) {
        var normalized = value.stripTrailingZeros();
        return normalized.signum() == 0 ? "0" : normalized.toPlainString();
    }

    private static byte[] hash(String value) {
        try {
            return MessageDigest.getInstance("SHA-256").digest(value.getBytes(StandardCharsets.UTF_8));
        } catch (NoSuchAlgorithmException impossible) {
            throw new IllegalStateException(impossible);
        }
    }

    public long countByInspectionId(String inspectionId) {
        return jdbc.queryForObject(
                """
                SELECT COUNT(*)
                FROM vision_inspection_results
                WHERE inspection_id_hash = ?
                AND inspection_id = ?
                """,
                Long.class,
                InspectionJdbcRepository.hash(inspectionId),
                inspectionId
        );
    }
}
