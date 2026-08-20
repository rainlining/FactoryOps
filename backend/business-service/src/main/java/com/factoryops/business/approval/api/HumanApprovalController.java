package com.factoryops.business.approval.api;

import com.factoryops.business.approval.application.ApprovalSecurity;
import com.factoryops.business.approval.application.ApprovedBatchHoldExecutionService;
import com.factoryops.business.approval.application.HumanApprovalApplicationService;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.*;
import tools.jackson.databind.JsonNode;

@RestController
public final class HumanApprovalController {
  private final HumanApprovalApplicationService service;
  private final ApprovalSecurity security;
  private final ApprovedBatchHoldExecutionService execution;

  public HumanApprovalController(HumanApprovalApplicationService service, ApprovalSecurity security,
      ApprovedBatchHoldExecutionService execution) {
    this.service = service;
    this.security = security;
    this.execution = execution;
  }

  @PostMapping("/internal/api/v1/approvals/{approvalKey}/execute")
  ActionExecutionResponse execute(
      @PathVariable String approvalKey,
      @RequestHeader(value = "X-FactoryOps-Service-Token", required = false) String token) {
    security.requireService(token);
    var outcome = execution.execute(approvalKey);
    return new ActionExecutionResponse(
        outcome.approvalKey(), outcome.action(), outcome.incidentId(), outcome.batchId(),
        outcome.status(), outcome.executedAt(), outcome.replayed());
  }

  @PostMapping("/internal/api/v1/approvals")
  ResponseEntity<ApprovalResponse> create(
      @RequestHeader(value = "X-FactoryOps-Service-Token", required = false) String token,
      @RequestBody JsonNode payload) {
    security.requireService(token);
    var outcome = service.create(payload);
    return ResponseEntity.status(outcome.replayed() ? 200 : 201)
        .body(new ApprovalResponse(outcome.approval(), outcome.replayed()));
  }

  @GetMapping("/api/v1/approvals/{approvalKey}")
  ApprovalResponse get(@PathVariable String approvalKey) {
    var outcome = service.get(approvalKey);
    return new ApprovalResponse(outcome.approval(), false);
  }

  @PostMapping("/api/v1/approvals/{approvalKey}/decision")
  ApprovalResponse decide(
      @PathVariable String approvalKey,
      @RequestHeader(value = "X-FactoryOps-Actor-Id", required = false) String actorId,
      @RequestHeader(value = "X-FactoryOps-Actor-Token", required = false) String actorToken,
      @RequestBody ApprovalDecisionRequest request) {
    var actor = security.requireActor(actorId, actorToken);
    var outcome = service.decide(
        approvalKey, actor, request.decision(), request.reason_code(), request.comment_ref());
    return new ApprovalResponse(outcome.approval(), outcome.replayed());
  }
}
