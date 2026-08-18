CREATE TABLE worker_task_execution_completion_requests (
  request_id VARCHAR(36) PRIMARY KEY,
  command_hash CHAR(64) NOT NULL,
  task_id VARCHAR(36) NOT NULL,
  execution_id VARCHAR(36) NOT NULL,
  final_status VARCHAR(16) NOT NULL,
  created_at TIMESTAMP(6) NOT NULL,
  CONSTRAINT fk_worker_completion_request_task FOREIGN KEY (task_id) REFERENCES agent_tasks(task_id) ON DELETE RESTRICT,
  CONSTRAINT fk_worker_completion_request_execution FOREIGN KEY (execution_id) REFERENCES agent_executions(execution_id) ON DELETE RESTRICT,
  CONSTRAINT chk_worker_completion_status CHECK (final_status IN ('SUCCEEDED','FAILED'))
) ENGINE=InnoDB;
