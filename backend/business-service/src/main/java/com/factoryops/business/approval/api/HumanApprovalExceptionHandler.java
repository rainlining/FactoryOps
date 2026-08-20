package com.factoryops.business.approval.api;

import com.factoryops.business.approval.application.ApprovalProblem;
import com.factoryops.business.inspection.api.ApiErrorResponse;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.ExceptionHandler;
import org.springframework.web.bind.annotation.RestControllerAdvice;

@RestControllerAdvice
public final class HumanApprovalExceptionHandler {
  @ExceptionHandler(ApprovalProblem.class)
  ResponseEntity<ApiErrorResponse> approval(ApprovalProblem problem) {
    return ResponseEntity.status(problem.status())
        .body(new ApiErrorResponse(problem.code(), problem.path(), problem.getMessage()));
  }
}
