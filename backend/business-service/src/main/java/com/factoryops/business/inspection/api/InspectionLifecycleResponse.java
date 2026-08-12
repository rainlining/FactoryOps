package com.factoryops.business.inspection.api;
import com.fasterxml.jackson.annotation.JsonProperty;
import java.time.Instant;
public record InspectionLifecycleResponse(@JsonProperty("inspection_id") String inspectionId,String status,Input input,@JsonProperty("created_at") Instant createdAt,@JsonProperty("completed_at") Instant completedAt,boolean replayed){public record Input(@JsonProperty("image_uri") String imageUri,String sha256){}}
