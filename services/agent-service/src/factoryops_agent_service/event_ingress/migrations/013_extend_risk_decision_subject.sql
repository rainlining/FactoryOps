ALTER TABLE risk_decisions
  ADD COLUMN subject_type VARCHAR(20) NULL AFTER decision_key,
  ADD COLUMN fusion_id VARCHAR(36) NULL AFTER recommendation_key,
  ADD COLUMN fusion_key CHAR(68) NULL AFTER fusion_id,
  ADD COLUMN coordinator_execution_id VARCHAR(36) NULL AFTER task_id,
  ADD COLUMN fusion_round INT UNSIGNED NULL AFTER coordinator_execution_id;

UPDATE risk_decisions SET subject_type='RECOMMENDATION' WHERE subject_type IS NULL;

ALTER TABLE risk_decisions
  MODIFY subject_type VARCHAR(20) NOT NULL,
  MODIFY recommendation_id VARCHAR(36) NULL,
  MODIFY recommendation_key CHAR(68) NULL,
  MODIFY task_id VARCHAR(36) NULL,
  ADD CONSTRAINT fk_risk_decision_fusion FOREIGN KEY (fusion_id) REFERENCES coordinator_fusions(fusion_id) ON DELETE RESTRICT,
  ADD CONSTRAINT fk_risk_decision_coordinator_execution FOREIGN KEY (coordinator_execution_id) REFERENCES agent_executions(execution_id) ON DELETE RESTRICT,
  ADD CONSTRAINT uk_risk_decision_fusion UNIQUE (fusion_id),
  ADD CONSTRAINT chk_risk_decision_subject CHECK (
    (subject_type='RECOMMENDATION' AND recommendation_id IS NOT NULL AND recommendation_key IS NOT NULL AND task_id IS NOT NULL AND fusion_id IS NULL AND fusion_key IS NULL AND coordinator_execution_id IS NULL AND fusion_round IS NULL)
    OR
    (subject_type='FUSION' AND recommendation_id IS NULL AND recommendation_key IS NULL AND task_id IS NULL AND fusion_id IS NOT NULL AND fusion_key IS NOT NULL AND coordinator_execution_id IS NOT NULL AND fusion_round IS NOT NULL)
  );
