CREATE TABLE agent_executions (
  execution_id VARCHAR(36) PRIMARY KEY,
  execution_key VARCHAR(68) NOT NULL,
  contract_version VARCHAR(20) NOT NULL,
  run_id VARCHAR(36) NOT NULL,
  agent_role VARCHAR(16) NOT NULL,
  attempt INT UNSIGNED NOT NULL,
  task_id VARCHAR(36) NULL,
  runtime_version VARCHAR(128) NOT NULL,
  prompt_version VARCHAR(128) NOT NULL,
  model_policy_version VARCHAR(128) NOT NULL,
  tool_policy_version VARCHAR(128) NOT NULL,
  context_policy_version VARCHAR(128) NOT NULL,
  code_revision VARCHAR(64) NOT NULL,
  context_snapshot_id VARCHAR(36) NOT NULL,
  input_evidence_refs JSON NOT NULL,
  status VARCHAR(16) NOT NULL,
  revision BIGINT UNSIGNED NOT NULL,
  created_at TIMESTAMP(6) NOT NULL,
  updated_at TIMESTAMP(6) NOT NULL,
  started_at TIMESTAMP(6) NULL,
  ended_at TIMESTAMP(6) NULL,
  status_reason_code VARCHAR(128) NULL,
  status_reason_message VARCHAR(500) NULL,
  output_artifact_refs JSON NULL,
  decision_id VARCHAR(36) NULL,
  result_evidence_refs JSON NULL,
  failure_code VARCHAR(128) NULL,
  failure_message VARCHAR(600) NULL,
  failure_recoverability VARCHAR(16) NULL,
  failed_dependency_ref VARCHAR(255) NULL,
  CONSTRAINT fk_agent_executions_run FOREIGN KEY (run_id) REFERENCES agent_runs(run_id) ON DELETE RESTRICT,
  CONSTRAINT fk_agent_executions_task FOREIGN KEY (task_id) REFERENCES agent_tasks(task_id) ON DELETE RESTRICT,
  CONSTRAINT chk_agent_executions_role CHECK ((agent_role='coordinator' AND task_id IS NULL) OR (agent_role IN ('quality','production','sla','risk') AND task_id IS NOT NULL)),
  CONSTRAINT chk_agent_executions_lifecycle CHECK (
    (status='PENDING' AND revision=0 AND started_at IS NULL AND ended_at IS NULL)
    OR (status='RUNNING' AND started_at IS NOT NULL AND ended_at IS NULL)
    OR (status IN ('SUCCEEDED','FAILED') AND started_at IS NOT NULL AND ended_at IS NOT NULL)
    OR (status='CANCELLED' AND ended_at IS NOT NULL)),
  CONSTRAINT chk_agent_executions_result CHECK (
    (status='SUCCEEDED' AND output_artifact_refs IS NOT NULL AND failure_code IS NULL)
    OR (status='FAILED' AND output_artifact_refs IS NULL AND failure_code IS NOT NULL AND failure_message IS NOT NULL AND failure_recoverability IS NOT NULL)
    OR (status NOT IN ('SUCCEEDED','FAILED') AND output_artifact_refs IS NULL AND decision_id IS NULL AND result_evidence_refs IS NULL AND failure_code IS NULL AND failure_message IS NULL AND failure_recoverability IS NULL AND failed_dependency_ref IS NULL)),
  UNIQUE KEY uk_agent_executions_key (execution_key),
  KEY idx_agent_executions_run_role (run_id, agent_role, created_at),
  KEY idx_agent_executions_task_attempt (task_id, attempt),
  KEY idx_agent_executions_status_updated (status, updated_at)
) ENGINE=InnoDB;

CREATE TABLE agent_execution_transitions (
  transition_id VARCHAR(36) PRIMARY KEY,
  transition_request_id VARCHAR(36) NOT NULL,
  execution_id VARCHAR(36) NOT NULL,
  from_status VARCHAR(16) NULL,
  to_status VARCHAR(16) NOT NULL,
  from_revision BIGINT UNSIGNED NULL,
  to_revision BIGINT UNSIGNED NOT NULL,
  actor_kind VARCHAR(32) NOT NULL,
  actor_id VARCHAR(255) NOT NULL,
  reason_code VARCHAR(128) NOT NULL,
  reason_message VARCHAR(500) NULL,
  result_json JSON NULL,
  failure_json JSON NULL,
  occurred_at TIMESTAMP(6) NOT NULL,
  CONSTRAINT fk_execution_transitions_execution FOREIGN KEY (execution_id) REFERENCES agent_executions(execution_id) ON DELETE RESTRICT,
  CONSTRAINT chk_execution_transitions_revision CHECK ((from_status IS NULL AND from_revision IS NULL AND to_status='PENDING' AND to_revision=0) OR (from_status IS NOT NULL AND from_revision IS NOT NULL AND to_revision=from_revision+1)),
  UNIQUE KEY uk_execution_transitions_request (transition_request_id),
  UNIQUE KEY uk_execution_transitions_revision (execution_id, to_revision)
) ENGINE=InnoDB;

ALTER TABLE agent_runs ADD CONSTRAINT fk_agent_runs_coordinator_execution FOREIGN KEY (coordinator_execution_id) REFERENCES agent_executions(execution_id) ON DELETE RESTRICT;
ALTER TABLE agent_tasks ADD CONSTRAINT fk_agent_tasks_created_by_execution FOREIGN KEY (created_by_execution_id) REFERENCES agent_executions(execution_id) ON DELETE RESTRICT;
ALTER TABLE agent_tasks ADD CONSTRAINT fk_agent_tasks_current_execution FOREIGN KEY (current_execution_id) REFERENCES agent_executions(execution_id) ON DELETE RESTRICT;
ALTER TABLE agent_tasks ADD CONSTRAINT fk_agent_tasks_completion_execution FOREIGN KEY (completion_execution_id) REFERENCES agent_executions(execution_id) ON DELETE RESTRICT;
ALTER TABLE agent_tasks ADD CONSTRAINT fk_agent_tasks_failure_execution FOREIGN KEY (failure_execution_id) REFERENCES agent_executions(execution_id) ON DELETE RESTRICT;
