CREATE TABLE human_approvals (
  approval_id VARCHAR(36) PRIMARY KEY,
  approval_key CHAR(68) NOT NULL UNIQUE,
  decision_id VARCHAR(36) NOT NULL UNIQUE,
  decision_key CHAR(68) NOT NULL UNIQUE,
  fusion_id VARCHAR(36) NOT NULL,
  fusion_key CHAR(68) NOT NULL,
  run_id VARCHAR(36) NOT NULL,
  coordinator_execution_id VARCHAR(36) NOT NULL,
  fusion_round INT UNSIGNED NOT NULL,
  revision INT UNSIGNED NOT NULL,
  status VARCHAR(16) NOT NULL,
  canonical_sha256 CHAR(64) NOT NULL,
  payload_json LONGTEXT NOT NULL,
  requested_at TIMESTAMP(6) NOT NULL,
  expires_at TIMESTAMP(6) NOT NULL,
  updated_at TIMESTAMP(6) NOT NULL,
  created_at TIMESTAMP(6) NOT NULL,
  CONSTRAINT fk_human_approval_decision FOREIGN KEY (decision_id) REFERENCES risk_decisions(decision_id) ON DELETE RESTRICT,
  CONSTRAINT fk_human_approval_fusion FOREIGN KEY (fusion_id) REFERENCES coordinator_fusions(fusion_id) ON DELETE RESTRICT,
  CONSTRAINT fk_human_approval_run FOREIGN KEY (run_id) REFERENCES agent_runs(run_id) ON DELETE RESTRICT,
  CONSTRAINT fk_human_approval_coordinator FOREIGN KEY (coordinator_execution_id) REFERENCES agent_executions(execution_id) ON DELETE RESTRICT,
  CONSTRAINT chk_human_approval_status CHECK (status IN ('PENDING','APPROVED','REJECTED','EXPIRED')),
  CONSTRAINT chk_human_approval_revision CHECK (revision IN (1,2)),
  CONSTRAINT chk_human_approval_payload CHECK (JSON_VALID(payload_json))
) ENGINE=InnoDB;

CREATE TABLE human_approval_history (
  approval_id VARCHAR(36) NOT NULL,
  revision INT UNSIGNED NOT NULL,
  status VARCHAR(16) NOT NULL,
  canonical_sha256 CHAR(64) NOT NULL,
  payload_json LONGTEXT NOT NULL,
  recorded_at TIMESTAMP(6) NOT NULL,
  PRIMARY KEY (approval_id, revision),
  CONSTRAINT fk_human_approval_history_current FOREIGN KEY (approval_id) REFERENCES human_approvals(approval_id) ON DELETE RESTRICT,
  CONSTRAINT chk_human_approval_history_status CHECK (status IN ('PENDING','APPROVED','REJECTED','EXPIRED')),
  CONSTRAINT chk_human_approval_history_payload CHECK (JSON_VALID(payload_json))
) ENGINE=InnoDB;
