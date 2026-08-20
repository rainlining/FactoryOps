package com.factoryops.business.approval.api;

public record ApprovalDecisionRequest(
    String decision,
    String reason_code,
    String comment_ref) {}
