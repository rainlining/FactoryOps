package com.factoryops.business.incident.api;

import com.factoryops.business.incident.application.QualityIncidentQueryService;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

@RestController
@RequestMapping("/api/v1/quality-incidents")
public class QualityIncidentController {
  private final QualityIncidentQueryService service;

  public QualityIncidentController(QualityIncidentQueryService service) {
    this.service = service;
  }

  @GetMapping("/{id}")
  QualityIncidentResponse get(@PathVariable String id) {
    var incident = service.get(id);
    return new QualityIncidentResponse(
        incident.incident().schemaVersion(),
        incident.incident().id(),
        incident.incident().status(),
        incident.incident().batchId(),
        incident.incident().inspectionId(),
        incident.incident().resultId(),
        incident.resultOriginKind(),
        incident.incident().createdAt());
  }
}
