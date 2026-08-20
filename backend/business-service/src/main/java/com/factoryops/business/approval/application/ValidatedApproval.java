package com.factoryops.business.approval.application;

import java.time.Instant;
import tools.jackson.databind.node.ObjectNode;

public record ValidatedApproval(
    String approvalId,
    String approvalKey,
    String decisionId,
    String decisionKey,
    String fusionId,
    String fusionKey,
    String runId,
    String coordinatorExecutionId,
    int round,
    String proposedAction,
    String riskLevel,
    Instant requestedAt,
    Instant expiresAt,
    int revision,
    String status,
    String actorId,
    Instant decidedAt,
    String reasonCode,
    String commentRef,
    ObjectNode payload,
    byte[] canonical,
    byte[] sha256) {}
