CREATE TABLE approved_action_executions (
    approval_id VARCHAR(36) NOT NULL PRIMARY KEY,
    approval_key VARCHAR(68) NOT NULL UNIQUE,
    action VARCHAR(32) NOT NULL,
    incident_id VARCHAR(67) NOT NULL,
    batch_id VARCHAR(64) NOT NULL,
    status VARCHAR(16) NOT NULL,
    executed_at TIMESTAMP(6) NOT NULL,
    CONSTRAINT fk_approved_action_approval FOREIGN KEY (approval_id)
      REFERENCES business_approvals(approval_id) ON DELETE RESTRICT,
    CONSTRAINT chk_approved_action CHECK (action='HOLD_BATCH'),
    CONSTRAINT chk_approved_action_status CHECK (status='EXECUTED')
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_bin;
