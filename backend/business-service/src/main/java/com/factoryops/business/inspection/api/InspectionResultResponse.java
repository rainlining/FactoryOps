package com.factoryops.business.inspection.api;

public record InspectionResultResponse(
    boolean replayed,
    String disposition,
    @com.fasterxml.jackson.annotation.JsonProperty("incident_id") String incidentId) {}
