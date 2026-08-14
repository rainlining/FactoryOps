CREATE TABLE outbox_events (
    event_id VARCHAR(68) NOT NULL,
    aggregate_type VARCHAR(64) NOT NULL,
    aggregate_id_hash BINARY(32) NOT NULL,
    aggregate_id VARCHAR(67) NOT NULL,
    event_type VARCHAR(128) NOT NULL,
    contract_version VARCHAR(16) NOT NULL,
    topic VARCHAR(249) NOT NULL,
    message_key VARCHAR(255) NOT NULL,
    occurred_at TIMESTAMP(6) NOT NULL,
    payload LONGTEXT NOT NULL,
    status VARCHAR(16) NOT NULL,
    attempt_count INT UNSIGNED NOT NULL,
    available_at TIMESTAMP(6) NOT NULL,
    published_at TIMESTAMP(6) NULL,
    last_error VARCHAR(2048) NULL,
    created_at TIMESTAMP(6) NOT NULL,
    PRIMARY KEY (event_id),
    UNIQUE KEY uq_outbox_aggregate_event (
        aggregate_type,
        aggregate_id_hash,
        event_type
    ),
    INDEX idx_outbox_publishable (
        status,
        available_at,
        created_at,
        event_id
    ),
    CONSTRAINT fk_outbox_quality_incident FOREIGN KEY (
        aggregate_id_hash,
        aggregate_id
    ) REFERENCES quality_incidents (
        incident_id_hash,
        incident_id
    ),
    CONSTRAINT chk_outbox_event_id CHECK (
        event_id REGEXP '^EVT-[0-9A-F]{64}$'
    ),
    CONSTRAINT chk_outbox_payload_json CHECK (JSON_VALID(payload)),
    CONSTRAINT chk_outbox_status CHECK (
        status IN ('PENDING', 'PUBLISHED')
    ),
    CONSTRAINT chk_outbox_publication_state CHECK (
        (status = 'PENDING' AND published_at IS NULL) OR
        (status = 'PUBLISHED' AND published_at IS NOT NULL)
    )
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_bin;

SET time_zone = '+00:00';
SET @outbox_migration_time = CURRENT_TIMESTAMP(6);

INSERT INTO outbox_events (
    event_id,
    aggregate_type,
    aggregate_id_hash,
    aggregate_id,
    event_type,
    contract_version,
    topic,
    message_key,
    occurred_at,
    payload,
    status,
    attempt_count,
    available_at,
    published_at,
    last_error,
    created_at
)
SELECT
    CONCAT('EVT-', UPPER(SHA2(CONCAT(
        'factoryops:event:quality.incident.opened:v1:',
        incident_id
    ), 256))),
    'quality-incident',
    incident_id_hash,
    incident_id,
    'quality.incident.opened',
    '1.0',
    'factoryops.quality.incident.v1',
    incident_id,
    created_at,
    CONCAT(
        '{"aggregate":{"id":', JSON_QUOTE(incident_id),
        ',"type":"quality-incident"}',
        ',"causation_id":', JSON_QUOTE(result_id),
        ',"contract_version":"1.0"',
        ',"correlation_id":', JSON_QUOTE(incident_id),
        ',"event_id":', JSON_QUOTE(CONCAT('EVT-', UPPER(SHA2(CONCAT(
            'factoryops:event:quality.incident.opened:v1:',
            incident_id
        ), 256)))),
        ',"event_type":"quality.incident.opened"',
        ',"occurred_at":', JSON_QUOTE(CONCAT(
            DATE_FORMAT(created_at, '%Y-%m-%dT%H:%i:%s.%f'),
            'Z'
        )),
        ',"payload":{"batch_id":', JSON_QUOTE(batch_id),
        ',"incident_id":', JSON_QUOTE(incident_id),
        ',"incident_schema_version":"1.0"',
        ',"inspection_id":', JSON_QUOTE(inspection_id),
        ',"result_id":', JSON_QUOTE(result_id),
        ',"status":"OPEN"}',
        ',"producer":{"name":"factoryops-business-service"',
        ',"version":"0.1.0"}}'
    ),
    'PENDING',
    0,
    @outbox_migration_time,
    NULL,
    NULL,
    @outbox_migration_time
FROM quality_incidents;
