CREATE TABLE worker_task_execution_retry_requests (
  request_id VARCHAR(36) PRIMARY KEY,
  command_hash CHAR(64) NOT NULL,
  task_id VARCHAR(36) NOT NULL,
  failed_execution_id VARCHAR(36) NOT NULL,
  new_execution_id VARCHAR(36) NOT NULL,
  created_at TIMESTAMP(6) NOT NULL,
  CONSTRAINT fk_worker_retry_request_task FOREIGN KEY (task_id) REFERENCES agent_tasks(task_id) ON DELETE RESTRICT,
  CONSTRAINT fk_worker_retry_failed_execution FOREIGN KEY (failed_execution_id) REFERENCES agent_executions(execution_id) ON DELETE RESTRICT,
  CONSTRAINT fk_worker_retry_new_execution FOREIGN KEY (new_execution_id) REFERENCES agent_executions(execution_id) ON DELETE RESTRICT
) ENGINE=InnoDB;
