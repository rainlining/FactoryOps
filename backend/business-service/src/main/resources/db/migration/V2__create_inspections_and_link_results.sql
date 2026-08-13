CREATE TABLE inspections (
    inspection_id_hash BINARY(32) NOT NULL PRIMARY KEY,
    inspection_id TEXT NOT NULL,
    expected_image_uri TEXT NOT NULL,
    expected_image_sha256 CHAR(64) NOT NULL,
    status VARCHAR(32) NOT NULL,
    created_at TIMESTAMP(6) NOT NULL,
    completed_at TIMESTAMP(6) NULL,
    CONSTRAINT chk_inspection_status CHECK (status IN ('PENDING', 'COMPLETED')),
    CONSTRAINT chk_inspection_completion CHECK (
        (status = 'PENDING' AND completed_at IS NULL) OR
        (status = 'COMPLETED' AND completed_at IS NOT NULL)
    )
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_bin;

INSERT INTO inspections
    (inspection_id_hash, inspection_id, expected_image_uri, expected_image_sha256, status, created_at, completed_at)
SELECT inspection_id_hash, MIN(inspection_id),
       MIN(JSON_UNQUOTE(JSON_EXTRACT(canonical_payload, '$.input.image_uri'))),
       MIN(JSON_UNQUOTE(JSON_EXTRACT(canonical_payload, '$.input.sha256'))),
       'COMPLETED', MIN(created_at), MIN(created_at)
FROM vision_inspection_results
GROUP BY inspection_id_hash
HAVING COUNT(DISTINCT CONCAT(
    JSON_UNQUOTE(JSON_EXTRACT(canonical_payload, '$.input.image_uri')), CHAR(0),
    JSON_UNQUOTE(JSON_EXTRACT(canonical_payload, '$.input.sha256'))
)) = 1;

ALTER TABLE vision_inspection_results
ADD CONSTRAINT fk_vision_result_inspection
FOREIGN KEY (inspection_id_hash) REFERENCES inspections(inspection_id_hash);
