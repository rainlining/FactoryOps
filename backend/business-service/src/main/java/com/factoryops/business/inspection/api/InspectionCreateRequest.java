package com.factoryops.business.inspection.api;

import com.fasterxml.jackson.annotation.JsonProperty;

public record InspectionCreateRequest(
    @JsonProperty("inspection_id") String inspectionId,
    @JsonProperty("batch_id") String batchId,
    Input input) {
  public record Input(@JsonProperty("image_uri") String imageUri, String sha256) {}
}
