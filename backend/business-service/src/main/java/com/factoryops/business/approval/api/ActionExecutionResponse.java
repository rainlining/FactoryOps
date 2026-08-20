package com.factoryops.business.approval.api;

import com.fasterxml.jackson.annotation.JsonProperty;
import java.time.Instant;

public record ActionExecutionResponse(
    @JsonProperty("approval_key") String approvalKey,
    String action,
    @JsonProperty("incident_id") String incidentId,
    @JsonProperty("batch_id") String batchId,
    String status,
    @JsonProperty("executed_at") Instant executedAt,
    boolean replayed) {}
