package com.factoryops.business.inspection.domain;

import java.time.Instant;

public final class Inspection {
    private final String id;
    private final String batchId;
    private final InspectionInput input;
    private final Instant createdAt;
    private InspectionStatus status;
    private Instant completedAt;

    private Inspection(String id, String batchId, InspectionInput input, InspectionStatus status, Instant createdAt, Instant completedAt) {
        if (id == null || id.isBlank()) throw new IllegalArgumentException("inspection_id must not be blank");
        if ((status == InspectionStatus.PENDING) != (completedAt == null)) throw new IllegalArgumentException("status and completed_at disagree");
        if(batchId==null||batchId.isBlank())throw new IllegalArgumentException("batch_id must not be blank");this.id = id; this.batchId=batchId; this.input = input; this.status = status; this.createdAt = createdAt; this.completedAt = completedAt;
    }

    public static Inspection pending(String id, String batchId, InspectionInput input, Instant createdAt) {
        return new Inspection(id, batchId, input, InspectionStatus.PENDING, createdAt, null);
    }

    public static Inspection restore(String id, String batchId, InspectionInput input, InspectionStatus status, Instant createdAt, Instant completedAt) {
        return new Inspection(id, batchId, input, status, createdAt, completedAt);
    }

    public void complete(Instant at) {
        if (status == InspectionStatus.PENDING) { status = InspectionStatus.COMPLETED; completedAt = at; }
    }

    public String id() { return id; }
    public String batchId(){return batchId;}
    public InspectionInput input() { return input; }
    public InspectionStatus status() { return status; }
    public Instant createdAt() { return createdAt; }
    public Instant completedAt() { return completedAt; }
}
