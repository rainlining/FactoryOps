package com.factoryops.business.approval.application;

import java.time.Instant;

public record ActionExecutionOutcome(
    String approvalKey,
    String action,
    String incidentId,
    String batchId,
    String status,
    Instant executedAt,
    boolean replayed) {}
