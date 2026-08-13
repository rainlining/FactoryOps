package com.factoryops.business.incident.api;

import com.fasterxml.jackson.annotation.JsonProperty;
import java.time.Instant;

public record QualityIncidentResponse(
    @JsonProperty("incident_schema_version") String incidentSchemaVersion,
    @JsonProperty("incident_id") String incidentId,
    String status,
    @JsonProperty("batch_id") String batchId,
    @JsonProperty("inspection_id") String inspectionId,
    @JsonProperty("result_id") String resultId,
    @JsonProperty("result_origin_kind") String resultOriginKind,
    @JsonProperty("created_at") Instant createdAt) {}
