CREATE TABLE agent_tasks (
  task_id VARCHAR(36) PRIMARY KEY,
  task_request_id VARCHAR(36) NOT NULL,
  task_key VARCHAR(68) NOT NULL,
  contract_version VARCHAR(20) NOT NULL,
  run_id VARCHAR(36) NOT NULL,
  task_type VARCHAR(32) NOT NULL,
  target_agent_role VARCHAR(32) NOT NULL,
  created_by_execution_id VARCHAR(36) NOT NULL,
  priority INT UNSIGNED NOT NULL,
  context_snapshot_id VARCHAR(36) NOT NULL,
  evidence_refs JSON NOT NULL,
  status VARCHAR(16) NOT NULL,
  revision BIGINT UNSIGNED NOT NULL,
  created_at TIMESTAMP(6) NOT NULL,
  updated_at TIMESTAMP(6) NOT NULL,
  started_at TIMESTAMP(6) NULL,
  ended_at TIMESTAMP(6) NULL,
  status_reason_code VARCHAR(128) NULL,
  status_reason_message VARCHAR(500) NULL,
  current_execution_id VARCHAR(36) NULL,
  attempt_count BIGINT UNSIGNED NOT NULL,
  completion_execution_id VARCHAR(36) NULL,
  failure_execution_id VARCHAR(36) NULL,
  failure_code VARCHAR(128) NULL,
  failure_message VARCHAR(600) NULL,
  failure_recoverability VARCHAR(16) NULL,
  CONSTRAINT fk_agent_tasks_run FOREIGN KEY (run_id) REFERENCES agent_runs(run_id) ON DELETE RESTRICT,
  CONSTRAINT chk_agent_tasks_priority CHECK (priority <= 100),
  CONSTRAINT chk_agent_tasks_lifecycle CHECK (
    (status='PENDING' AND revision=0 AND started_at IS NULL AND ended_at IS NULL AND current_execution_id IS NULL AND attempt_count=0)
    OR (status='RUNNING' AND started_at IS NOT NULL AND ended_at IS NULL AND current_execution_id IS NOT NULL AND attempt_count>=1)
    OR (status IN ('SUCCEEDED','FAILED') AND started_at IS NOT NULL AND ended_at IS NOT NULL AND current_execution_id IS NOT NULL AND attempt_count>=1)
    OR (status IN ('CANCELLED','SKIPPED') AND ended_at IS NOT NULL)
  ),
  CONSTRAINT chk_agent_tasks_result CHECK (
    (status='SUCCEEDED' AND completion_execution_id=current_execution_id
      AND failure_execution_id IS NULL AND failure_code IS NULL AND failure_message IS NULL AND failure_recoverability IS NULL)
    OR (status='FAILED' AND failure_execution_id=current_execution_id AND completion_execution_id IS NULL
      AND failure_code IS NOT NULL AND failure_message IS NOT NULL AND failure_recoverability='non_retryable')
    OR (status NOT IN ('SUCCEEDED','FAILED') AND completion_execution_id IS NULL AND failure_execution_id IS NULL
      AND failure_code IS NULL AND failure_message IS NULL AND failure_recoverability IS NULL)
  ),
  UNIQUE KEY uk_agent_tasks_request (task_request_id),
  UNIQUE KEY uk_agent_tasks_key (task_key),
  KEY idx_agent_tasks_run_status (run_id, status, priority),
  KEY idx_agent_tasks_status_updated (status, updated_at)
) ENGINE=InnoDB;

CREATE TABLE agent_task_dependencies (
  task_id VARCHAR(36) NOT NULL,
  dependency_task_id VARCHAR(36) NOT NULL,
  ordinal INT UNSIGNED NOT NULL,
  PRIMARY KEY (task_id, dependency_task_id),
  UNIQUE KEY uk_task_dependencies_ordinal (task_id, ordinal),
  CONSTRAINT fk_task_dependencies_task FOREIGN KEY (task_id) REFERENCES agent_tasks(task_id) ON DELETE RESTRICT,
  CONSTRAINT fk_task_dependencies_dependency FOREIGN KEY (dependency_task_id) REFERENCES agent_tasks(task_id) ON DELETE RESTRICT,
  CONSTRAINT chk_task_dependencies_self CHECK (task_id <> dependency_task_id)
) ENGINE=InnoDB;

CREATE TABLE agent_task_transitions (
  transition_id VARCHAR(36) PRIMARY KEY,
  transition_request_id VARCHAR(36) NOT NULL,
  task_id VARCHAR(36) NOT NULL,
  from_status VARCHAR(16) NULL,
  to_status VARCHAR(16) NOT NULL,
  from_revision BIGINT UNSIGNED NULL,
  to_revision BIGINT UNSIGNED NOT NULL,
  actor_kind VARCHAR(32) NOT NULL,
  actor_id VARCHAR(255) NOT NULL,
  reason_code VARCHAR(128) NOT NULL,
  reason_message VARCHAR(500) NULL,
  execution_id VARCHAR(36) NULL,
  attempt_count BIGINT UNSIGNED NOT NULL,
  completion_execution_id VARCHAR(36) NULL,
  failure_code VARCHAR(128) NULL,
  failure_message VARCHAR(600) NULL,
  failure_recoverability VARCHAR(16) NULL,
  occurred_at TIMESTAMP(6) NOT NULL,
  CONSTRAINT fk_task_transitions_task FOREIGN KEY (task_id) REFERENCES agent_tasks(task_id) ON DELETE RESTRICT,
  CONSTRAINT chk_task_transitions_revision CHECK (
    (from_status IS NULL AND from_revision IS NULL AND to_status='PENDING' AND to_revision=0)
    OR (from_status IS NOT NULL AND from_revision IS NOT NULL AND to_revision=from_revision+1)
  ),
  UNIQUE KEY uk_task_transitions_request (transition_request_id),
  UNIQUE KEY uk_task_transitions_task_revision (task_id, to_revision)
) ENGINE=InnoDB;
