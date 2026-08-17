CREATE TABLE coordinator_start_requests (
  start_request_id VARCHAR(36) PRIMARY KEY,
  run_id VARCHAR(36) NOT NULL,
  execution_id VARCHAR(36) NOT NULL,
  payload_sha256 BINARY(32) NOT NULL,
  created_at TIMESTAMP(6) NOT NULL,
  CONSTRAINT fk_coordinator_start_run FOREIGN KEY (run_id) REFERENCES agent_runs(run_id) ON DELETE RESTRICT,
  CONSTRAINT fk_coordinator_start_execution FOREIGN KEY (execution_id) REFERENCES agent_executions(execution_id) ON DELETE RESTRICT,
  UNIQUE KEY uk_coordinator_start_run (run_id),
  UNIQUE KEY uk_coordinator_start_execution (execution_id)
) ENGINE=InnoDB;
