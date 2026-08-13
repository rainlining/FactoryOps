CREATE TABLE batches (
 batch_id_hash BINARY(32) PRIMARY KEY, batch_id VARCHAR(64) NOT NULL,
 kind VARCHAR(32) NOT NULL, product_code VARCHAR(64) NOT NULL, production_line VARCHAR(64) NOT NULL,
 status VARCHAR(32) NOT NULL, created_at TIMESTAMP(6) NOT NULL, held_at TIMESTAMP(6) NULL,
 hold_reason_code VARCHAR(64) NULL, hold_reason_detail VARCHAR(500) NULL,
 hold_inspection_id_hash BINARY(32) NULL, hold_inspection_id TEXT NULL,
 hold_result_id_hash BINARY(32) NULL, hold_result_id TEXT NULL,
 released_at TIMESTAMP(6) NULL, release_reason_code VARCHAR(64) NULL, release_reason_detail VARCHAR(500) NULL,
 CONSTRAINT chk_batch_kind CHECK(kind IN ('PRODUCTION','LEGACY_UNASSIGNED')),
 CONSTRAINT chk_batch_status CHECK(status IN ('OPEN','HELD','RELEASED')),
 CONSTRAINT chk_batch_state CHECK(
  (status='OPEN' AND held_at IS NULL AND hold_reason_code IS NULL AND released_at IS NULL AND release_reason_code IS NULL) OR
  (status='HELD' AND held_at IS NOT NULL AND hold_reason_code IS NOT NULL AND released_at IS NULL AND release_reason_code IS NULL) OR
  (status='RELEASED' AND held_at IS NOT NULL AND hold_reason_code IS NOT NULL AND released_at IS NOT NULL AND release_reason_code IS NOT NULL)),
 CONSTRAINT chk_batch_evidence CHECK(
  (hold_reason_code='QUALITY_ANOMALY' AND hold_inspection_id_hash IS NOT NULL AND hold_inspection_id IS NOT NULL AND hold_result_id_hash IS NOT NULL AND hold_result_id IS NOT NULL) OR
  (hold_reason_code<>'QUALITY_ANOMALY' AND hold_inspection_id_hash IS NULL AND hold_inspection_id IS NULL AND hold_result_id_hash IS NULL AND hold_result_id IS NULL) OR hold_reason_code IS NULL)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_bin;

SET @migration_time = CURRENT_TIMESTAMP(6);
INSERT INTO batches VALUES (UNHEX(SHA2('SYS-LEGACY-UNASSIGNED',256)),'SYS-LEGACY-UNASSIGNED','LEGACY_UNASSIGNED','SYS-LEGACY','SYS-LEGACY','RELEASED',@migration_time,@migration_time,'MIGRATED_LEGACY_DATA',NULL,NULL,NULL,NULL,NULL,@migration_time,'MIGRATED_LEGACY_DATA',NULL);
ALTER TABLE inspections ADD batch_id_hash BINARY(32) NULL, ADD batch_id VARCHAR(64) NULL;
UPDATE inspections SET batch_id_hash=UNHEX(SHA2('SYS-LEGACY-UNASSIGNED',256)),batch_id='SYS-LEGACY-UNASSIGNED';
ALTER TABLE inspections MODIFY batch_id_hash BINARY(32) NOT NULL, MODIFY batch_id VARCHAR(64) NOT NULL,
 ADD CONSTRAINT fk_inspection_batch FOREIGN KEY(batch_id_hash) REFERENCES batches(batch_id_hash);
ALTER TABLE batches ADD CONSTRAINT fk_batch_hold_inspection FOREIGN KEY(hold_inspection_id_hash) REFERENCES inspections(inspection_id_hash),
 ADD CONSTRAINT fk_batch_hold_result FOREIGN KEY(hold_result_id_hash) REFERENCES vision_inspection_results(result_id_hash);
