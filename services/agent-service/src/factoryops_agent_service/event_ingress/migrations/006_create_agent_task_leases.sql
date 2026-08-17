CREATE TABLE agent_task_leases (
  task_id VARCHAR(36) PRIMARY KEY,
  owner_id VARCHAR(255) NOT NULL,
  lease_token VARCHAR(64) NOT NULL,
  leased_at TIMESTAMP(6) NOT NULL,
  expires_at TIMESTAMP(6) NOT NULL,
  CONSTRAINT fk_task_lease_task FOREIGN KEY (task_id) REFERENCES agent_tasks(task_id) ON DELETE RESTRICT,
  UNIQUE KEY uk_task_lease_token (lease_token),
  KEY idx_task_lease_expiry (expires_at)
) ENGINE=InnoDB;
