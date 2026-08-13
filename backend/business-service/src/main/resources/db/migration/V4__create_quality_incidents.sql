ALTER TABLE batches
    ADD UNIQUE KEY uq_batch_identity (batch_id_hash, batch_id);

ALTER TABLE inspections
    ADD UNIQUE KEY uq_inspection_evidence (inspection_id_hash, batch_id_hash);

ALTER TABLE vision_inspection_results
    ADD UNIQUE KEY uq_result_evidence (result_id_hash, inspection_id_hash);

CREATE TABLE quality_incidents (
    incident_id_hash BINARY(32) NOT NULL,
    incident_id VARCHAR(67) NOT NULL,
    incident_schema_version VARCHAR(16) NOT NULL,
    status VARCHAR(32) NOT NULL,
    batch_id_hash BINARY(32) NOT NULL,
    batch_id VARCHAR(64) NOT NULL,
    inspection_id_hash BINARY(32) NOT NULL,
    inspection_id TEXT NOT NULL,
    result_id_hash BINARY(32) NOT NULL,
    result_id TEXT NOT NULL,
    created_at TIMESTAMP(6) NOT NULL,
    PRIMARY KEY (incident_id_hash),
    UNIQUE KEY uq_incident_id (incident_id_hash, incident_id),
    UNIQUE KEY uq_incident_result (result_id_hash),
    CONSTRAINT chk_incident_version CHECK (incident_schema_version = '1.0'),
    CONSTRAINT chk_incident_status CHECK (status = 'OPEN'),
    CONSTRAINT fk_incident_batch FOREIGN KEY (batch_id_hash)
        REFERENCES batches(batch_id_hash),
    CONSTRAINT fk_incident_inspection FOREIGN KEY
        (inspection_id_hash, batch_id_hash)
        REFERENCES inspections(inspection_id_hash, batch_id_hash),
    CONSTRAINT fk_incident_result FOREIGN KEY
        (result_id_hash, inspection_id_hash)
        REFERENCES vision_inspection_results(result_id_hash, inspection_id_hash)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_bin;

INSERT INTO quality_incidents (
    incident_id_hash, incident_id, incident_schema_version, status,
    batch_id_hash, batch_id, inspection_id_hash, inspection_id,
    result_id_hash, result_id, created_at)
SELECT
    UNHEX(SHA2(CONCAT('QI-', UPPER(SHA2(CONCAT(
        'factoryops:quality-incident:v1:result:', r.result_id), 256))), 256)),
    CONCAT('QI-', UPPER(SHA2(CONCAT(
        'factoryops:quality-incident:v1:result:', r.result_id), 256))),
    '1.0', 'OPEN', i.batch_id_hash, i.batch_id,
    r.inspection_id_hash, r.inspection_id, r.result_id_hash, r.result_id, r.created_at
FROM vision_inspection_results r
JOIN inspections i ON i.inspection_id_hash = r.inspection_id_hash
    AND i.inspection_id = r.inspection_id
WHERE JSON_EXTRACT(r.canonical_payload, '$.observation.is_anomaly') = TRUE;
