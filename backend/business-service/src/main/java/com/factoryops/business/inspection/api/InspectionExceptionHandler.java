package com.factoryops.business.inspection.api;

import com.factoryops.business.inspection.application.ResultIdentityConflictException;
import com.factoryops.business.inspection.application.VisionContractException;
import org.springframework.http.HttpStatus;
import org.springframework.http.ResponseEntity;
import org.springframework.http.converter.HttpMessageNotReadableException;
import org.springframework.web.bind.annotation.ExceptionHandler;
import org.springframework.web.bind.annotation.RestControllerAdvice;

@RestControllerAdvice
public class InspectionExceptionHandler {
    @ExceptionHandler(HttpMessageNotReadableException.class)
    ResponseEntity<ApiErrorResponse> malformed(HttpMessageNotReadableException error) {
        return ResponseEntity.badRequest().body(new ApiErrorResponse("malformed_json", "$", "Request is not valid JSON"));
    }

    @ExceptionHandler(VisionContractException.class)
    ResponseEntity<ApiErrorResponse> contract(VisionContractException error) {
        var issue = error.issue();
        return ResponseEntity.unprocessableEntity().body(new ApiErrorResponse(issue.code(), issue.path(), issue.message()));
    }

    @ExceptionHandler(ResultIdentityConflictException.class)
    ResponseEntity<ApiErrorResponse> conflict(ResultIdentityConflictException error) {
        return ResponseEntity.status(HttpStatus.CONFLICT)
                .body(new ApiErrorResponse("result_identity_conflict", "$.result_id", error.getMessage()));
    }
}
