package com.factoryops.business.inspection.api;

import com.factoryops.business.inspection.application.ResultIdentityConflictException;
import com.factoryops.business.inspection.application.VisionContractException;
import com.factoryops.business.inspection.application.InspectionIdentityConflictException;
import com.factoryops.business.inspection.application.InspectionNotFoundException;
import org.springframework.http.HttpStatus;
import org.springframework.http.ResponseEntity;
import org.springframework.http.converter.HttpMessageNotReadableException;
import org.springframework.web.bind.annotation.ExceptionHandler;
import org.springframework.web.bind.annotation.RestControllerAdvice;

@RestControllerAdvice
public class InspectionExceptionHandler {
    @ExceptionHandler(InspectionIdentityConflictException.class)
    ResponseEntity<ApiErrorResponse> inspectionConflict(InspectionIdentityConflictException error) { return ResponseEntity.status(HttpStatus.CONFLICT).body(new ApiErrorResponse("inspection_identity_conflict","$.inspection_id",error.getMessage())); }
    @ExceptionHandler(InspectionNotFoundException.class)
    ResponseEntity<ApiErrorResponse> inspectionMissing(InspectionNotFoundException error) { return ResponseEntity.status(HttpStatus.NOT_FOUND).body(new ApiErrorResponse("inspection_not_found","$.inspection_id",error.getMessage())); }
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
