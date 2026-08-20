package com.factoryops.business.approval.api;

import com.factoryops.business.approval.application.ApprovalSecurity;
import com.factoryops.business.approval.application.HumanApprovalApplicationService;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.*;
import tools.jackson.databind.JsonNode;

@RestController
public final class HumanApprovalController {
  private final HumanApprovalApplicationService service;
  private final ApprovalSecurity security;

  public HumanApprovalController(HumanApprovalApplicationService service, ApprovalSecurity security) {
    this.service = service;
    this.security = security;
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
      @RequestBody ApprovalDecisionRequest request) {
    var actor = security.requireActor(actorId);
    var outcome = service.decide(
        approvalKey, actor, request.decision(), request.reason_code(), request.comment_ref());
    return new ApprovalResponse(outcome.approval(), outcome.replayed());
  }
}
