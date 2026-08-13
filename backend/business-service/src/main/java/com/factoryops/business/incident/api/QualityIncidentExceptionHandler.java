package com.factoryops.business.incident.api;

import com.factoryops.business.incident.application.QualityIncidentNotFoundException;
import com.factoryops.business.inspection.api.ApiErrorResponse;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.ExceptionHandler;
import org.springframework.web.bind.annotation.RestControllerAdvice;

@RestControllerAdvice
public class QualityIncidentExceptionHandler {
  @ExceptionHandler(QualityIncidentNotFoundException.class)
  ResponseEntity<ApiErrorResponse> notFound() {
    return ResponseEntity.status(404).body(new ApiErrorResponse(
        "quality_incident_not_found", "$.incident_id", "Quality incident not found"));
  }
}
