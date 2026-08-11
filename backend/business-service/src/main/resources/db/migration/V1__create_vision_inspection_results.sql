CREATE TABLE vision_inspection_results (
    result_id_hash BINARY(32) NOT NULL,
    result_id TEXT NOT NULL,
    inspection_id_hash BINARY(32) NOT NULL,
    inspection_id TEXT NOT NULL,
    origin_kind VARCHAR(32) NOT NULL,
    anomaly_score_text TEXT NOT NULL,
    decision_threshold_text TEXT NOT NULL,
    canonical_payload LONGTEXT NOT NULL,
    payload_hash BINARY(32) NOT NULL,
    created_at TIMESTAMP(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
    PRIMARY KEY (result_id_hash),
    INDEX idx_vision_results_inspection (inspection_id_hash)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_bin;
