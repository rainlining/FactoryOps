CREATE TABLE coordinator_fusions (
  fusion_id VARCHAR(36) PRIMARY KEY,
  fusion_key CHAR(68) NOT NULL UNIQUE,
  run_id VARCHAR(36) NOT NULL,
  coordinator_execution_id VARCHAR(36) NOT NULL,
  fusion_round INT UNSIGNED NOT NULL,
  proposed_action VARCHAR(32) NOT NULL,
  has_conflict BOOLEAN NOT NULL,
  canonical_sha256 CHAR(64) NOT NULL,
  payload_json LONGTEXT NOT NULL,
  generated_at TIMESTAMP(6) NOT NULL,
  created_at TIMESTAMP(6) NOT NULL,
  CONSTRAINT fk_coordinator_fusion_run FOREIGN KEY (run_id) REFERENCES agent_runs(run_id) ON DELETE RESTRICT,
  CONSTRAINT fk_coordinator_fusion_execution FOREIGN KEY (coordinator_execution_id) REFERENCES agent_executions(execution_id) ON DELETE RESTRICT,
  CONSTRAINT uk_coordinator_fusion_round UNIQUE (coordinator_execution_id, fusion_round),
  CONSTRAINT chk_coordinator_fusion_payload CHECK (JSON_VALID(payload_json))
) ENGINE=InnoDB;

CREATE TABLE coordinator_fusion_recommendations (
  fusion_id VARCHAR(36) NOT NULL,
  recommendation_id VARCHAR(36) NOT NULL,
  recommendation_key CHAR(68) NOT NULL,
  agent_role VARCHAR(16) NOT NULL,
  PRIMARY KEY (fusion_id, recommendation_id),
  CONSTRAINT fk_fusion_recommendation_fusion FOREIGN KEY (fusion_id) REFERENCES coordinator_fusions(fusion_id) ON DELETE RESTRICT,
  CONSTRAINT fk_fusion_recommendation_source FOREIGN KEY (recommendation_id) REFERENCES specialist_recommendations(recommendation_id) ON DELETE RESTRICT,
  CONSTRAINT uk_fusion_recommendation_role UNIQUE (fusion_id, agent_role),
  CONSTRAINT uk_fusion_recommendation_key UNIQUE (fusion_id, recommendation_key),
  CONSTRAINT chk_fusion_recommendation_role CHECK (agent_role IN ('quality','production','sla'))
) ENGINE=InnoDB;
