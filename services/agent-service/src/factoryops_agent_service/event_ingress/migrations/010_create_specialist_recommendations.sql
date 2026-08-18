CREATE TABLE specialist_recommendations (
  recommendation_id VARCHAR(36) PRIMARY KEY,
  recommendation_key CHAR(68) NOT NULL UNIQUE,
  execution_id VARCHAR(36) NOT NULL UNIQUE,
  run_id VARCHAR(36) NOT NULL,
  task_id VARCHAR(36) NOT NULL,
  agent_role VARCHAR(16) NOT NULL,
  action VARCHAR(32) NOT NULL,
  severity VARCHAR(16) NOT NULL,
  canonical_sha256 CHAR(64) NOT NULL,
  payload_json LONGTEXT NOT NULL,
  generated_at TIMESTAMP(6) NOT NULL,
  created_at TIMESTAMP(6) NOT NULL,
  CONSTRAINT fk_specialist_recommendation_execution FOREIGN KEY (execution_id) REFERENCES agent_executions(execution_id) ON DELETE RESTRICT,
  CONSTRAINT fk_specialist_recommendation_run FOREIGN KEY (run_id) REFERENCES agent_runs(run_id) ON DELETE RESTRICT,
  CONSTRAINT fk_specialist_recommendation_task FOREIGN KEY (task_id) REFERENCES agent_tasks(task_id) ON DELETE RESTRICT,
  CONSTRAINT chk_specialist_recommendation_role CHECK (agent_role IN ('quality','production','sla')),
  CONSTRAINT chk_specialist_recommendation_payload CHECK (JSON_VALID(payload_json))
) ENGINE=InnoDB;
