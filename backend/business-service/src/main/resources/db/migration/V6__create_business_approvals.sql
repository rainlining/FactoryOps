CREATE TABLE business_approvals (
    approval_id VARCHAR(36) NOT NULL PRIMARY KEY,
    approval_key VARCHAR(68) NOT NULL UNIQUE,
    decision_id VARCHAR(36) NOT NULL,
    decision_key VARCHAR(68) NOT NULL,
    fusion_id VARCHAR(36) NOT NULL,
    fusion_key VARCHAR(68) NOT NULL,
    run_id VARCHAR(36) NOT NULL,
    coordinator_execution_id VARCHAR(36) NOT NULL,
    fusion_round INT UNSIGNED NOT NULL,
    proposed_action VARCHAR(32) NOT NULL,
    risk_level VARCHAR(16) NOT NULL,
    requested_at TIMESTAMP(6) NOT NULL,
    expires_at TIMESTAMP(6) NOT NULL,
    revision TINYINT UNSIGNED NOT NULL,
    status VARCHAR(16) NOT NULL,
    actor_id VARCHAR(128) NULL,
    decided_at TIMESTAMP(6) NULL,
    outcome_reason_code VARCHAR(128) NULL,
    comment_ref VARCHAR(255) NULL,
    canonical_sha256 BINARY(32) NOT NULL,
    payload LONGTEXT NOT NULL,
    created_at TIMESTAMP(6) NOT NULL,
    updated_at TIMESTAMP(6) NOT NULL,
    CONSTRAINT chk_business_approval_payload CHECK (JSON_VALID(payload)),
    CONSTRAINT chk_business_approval_status CHECK (status IN ('PENDING','APPROVED','REJECTED')),
    CONSTRAINT chk_business_approval_revision CHECK (
      (status='PENDING' AND revision=1 AND actor_id IS NULL AND decided_at IS NULL) OR
      (status IN ('APPROVED','REJECTED') AND revision=2 AND actor_id IS NOT NULL AND decided_at IS NOT NULL)
    ),
    CONSTRAINT chk_business_approval_window CHECK (requested_at < expires_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_bin;

CREATE TABLE business_approval_history (
    approval_id VARCHAR(36) NOT NULL,
    revision TINYINT UNSIGNED NOT NULL,
    status VARCHAR(16) NOT NULL,
    actor_id VARCHAR(128) NULL,
    canonical_sha256 BINARY(32) NOT NULL,
    payload LONGTEXT NOT NULL,
    recorded_at TIMESTAMP(6) NOT NULL,
    PRIMARY KEY (approval_id, revision),
    CONSTRAINT fk_business_approval_history_current FOREIGN KEY (approval_id)
      REFERENCES business_approvals(approval_id) ON DELETE RESTRICT,
    CONSTRAINT chk_business_approval_history_payload CHECK (JSON_VALID(payload)),
    CONSTRAINT chk_business_approval_history_status CHECK (status IN ('PENDING','APPROVED','REJECTED'))
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_bin;
