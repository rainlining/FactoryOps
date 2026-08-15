CREATE TABLE agent_runs (
  run_id VARCHAR(36) PRIMARY KEY,
  contract_version VARCHAR(20) NOT NULL,
  run_kind VARCHAR(8) NOT NULL,
  original_run_id VARCHAR(36) NOT NULL,
  trigger_event_id VARCHAR(68) NULL,
  replayed_from_run_id VARCHAR(36) NULL,
  replay_request_id VARCHAR(36) NULL,
  incident_id VARCHAR(67) NOT NULL,
  runtime_version VARCHAR(128) NOT NULL,
  workflow_version VARCHAR(128) NOT NULL,
  prompt_set_version VARCHAR(128) NOT NULL,
  model_policy_version VARCHAR(128) NOT NULL,
  tool_policy_version VARCHAR(128) NOT NULL,
  context_policy_version VARCHAR(128) NOT NULL,
  code_revision VARCHAR(64) NOT NULL,
  status VARCHAR(32) NOT NULL,
  revision BIGINT UNSIGNED NOT NULL,
  created_at TIMESTAMP(6) NOT NULL,
  updated_at TIMESTAMP(6) NOT NULL,
  started_at TIMESTAMP(6) NULL,
  ended_at TIMESTAMP(6) NULL,
  status_reason_code VARCHAR(128) NULL,
  status_reason_message VARCHAR(500) NULL,
  coordinator_execution_id VARCHAR(255) NULL,
  latest_checkpoint_id VARCHAR(255) NULL,
  agent_execution_count BIGINT UNSIGNED NOT NULL,
  task_count BIGINT UNSIGNED NOT NULL,
  completed_task_count BIGINT UNSIGNED NOT NULL,
  CONSTRAINT fk_agent_runs_trigger_event
    FOREIGN KEY (trigger_event_id)
    REFERENCES agent_event_inbox(event_id)
    ON DELETE RESTRICT,
  CONSTRAINT fk_agent_runs_original
    FOREIGN KEY (original_run_id)
    REFERENCES agent_runs(run_id)
    ON DELETE RESTRICT,
  CONSTRAINT fk_agent_runs_replayed_from
    FOREIGN KEY (replayed_from_run_id)
    REFERENCES agent_runs(run_id)
    ON DELETE RESTRICT,
  CONSTRAINT chk_agent_runs_identity CHECK (
    (
      run_kind = 'original'
      AND original_run_id = run_id
      AND trigger_event_id IS NOT NULL
      AND replayed_from_run_id IS NULL
      AND replay_request_id IS NULL
    )
    OR
    (
      run_kind = 'replay'
      AND original_run_id <> run_id
      AND trigger_event_id IS NULL
      AND replayed_from_run_id IS NOT NULL
      AND replayed_from_run_id <> run_id
      AND replay_request_id IS NOT NULL
    )
  ),
  CONSTRAINT chk_agent_runs_lifecycle CHECK (
    (
      status = 'PENDING'
      AND started_at IS NULL
      AND ended_at IS NULL
    )
    OR
    (
      status IN ('RUNNING', 'WAITING_FOR_APPROVAL', 'SUSPENDED')
      AND started_at IS NOT NULL
      AND ended_at IS NULL
    )
    OR
    (
      status IN ('SUCCEEDED', 'FAILED')
      AND started_at IS NOT NULL
      AND ended_at IS NOT NULL
    )
    OR
    (
      status = 'CANCELLED'
      AND ended_at IS NOT NULL
    )
  ),
  CONSTRAINT chk_agent_runs_reason CHECK (
    (
      status = 'PENDING'
      AND status_reason_code IS NULL
      AND status_reason_message IS NULL
    )
    OR
    (
      status <> 'PENDING'
      AND status_reason_code IS NOT NULL
      AND CHAR_LENGTH(status_reason_code) BETWEEN 3 AND 128
      AND (
        status_reason_message IS NULL
        OR CHAR_LENGTH(status_reason_message) BETWEEN 1 AND 500
      )
    )
  ),
  CONSTRAINT chk_agent_runs_suspended CHECK (
    status <> 'SUSPENDED'
    OR latest_checkpoint_id IS NOT NULL
  ),
  CONSTRAINT chk_agent_runs_progress CHECK (
    completed_task_count <= task_count
  ),
  UNIQUE KEY uk_agent_runs_trigger_event (trigger_event_id),
  UNIQUE KEY uk_agent_runs_replay_request (replay_request_id),
  KEY idx_agent_runs_incident_created (incident_id, created_at),
  KEY idx_agent_runs_original_created (original_run_id, created_at),
  KEY idx_agent_runs_status_updated (status, updated_at)
) ENGINE=InnoDB;

CREATE TABLE agent_run_transitions (
  transition_id VARCHAR(36) PRIMARY KEY,
  transition_request_id VARCHAR(36) NOT NULL,
  run_id VARCHAR(36) NOT NULL,
  from_status VARCHAR(32) NULL,
  to_status VARCHAR(32) NOT NULL,
  from_revision BIGINT UNSIGNED NULL,
  to_revision BIGINT UNSIGNED NOT NULL,
  actor_kind VARCHAR(32) NOT NULL,
  actor_id VARCHAR(255) NOT NULL,
  reason_code VARCHAR(128) NOT NULL,
  reason_message VARCHAR(500) NULL,
  checkpoint_id VARCHAR(255) NULL,
  occurred_at TIMESTAMP(6) NOT NULL,
  CONSTRAINT fk_run_transitions_run
    FOREIGN KEY (run_id)
    REFERENCES agent_runs(run_id)
    ON DELETE RESTRICT,
  CONSTRAINT chk_run_transitions_revision CHECK (
    (
      from_status IS NULL
      AND from_revision IS NULL
      AND to_status = 'PENDING'
      AND to_revision = 0
    )
    OR
    (
      from_status IS NOT NULL
      AND from_revision IS NOT NULL
      AND to_revision = from_revision + 1
    )
  ),
  CONSTRAINT chk_run_transitions_suspended CHECK (
    to_status <> 'SUSPENDED'
    OR checkpoint_id IS NOT NULL
  ),
  UNIQUE KEY uk_run_transitions_request (transition_request_id),
  UNIQUE KEY uk_run_transitions_run_revision (run_id, to_revision)
) ENGINE=InnoDB;
