CREATE TABLE agent_event_inbox (
  event_id VARCHAR(68) PRIMARY KEY,
  event_type VARCHAR(100) NOT NULL,
  contract_version VARCHAR(20) NOT NULL,
  topic VARCHAR(249) NOT NULL,
  kafka_partition INT NOT NULL,
  kafka_offset BIGINT NOT NULL,
  message_key VARCHAR(255) NOT NULL,
  raw_payload LONGBLOB NOT NULL,
  canonical_sha256 BINARY(32) NOT NULL,
  received_at TIMESTAMP(6) NOT NULL,
  UNIQUE KEY uk_inbox_source (topic, kafka_partition, kafka_offset)
) ENGINE=InnoDB;

CREATE TABLE agent_event_rejections (
  topic VARCHAR(249) NOT NULL,
  kafka_partition INT NOT NULL,
  kafka_offset BIGINT NOT NULL,
  event_id VARCHAR(68) NULL,
  reason_code VARCHAR(100) NOT NULL,
  reason_detail VARCHAR(1024) NOT NULL,
  payload_sha256 BINARY(32) NOT NULL,
  rejected_at TIMESTAMP(6) NOT NULL,
  PRIMARY KEY (topic, kafka_partition, kafka_offset),
  KEY idx_rejection_event (event_id)
) ENGINE=InnoDB;
