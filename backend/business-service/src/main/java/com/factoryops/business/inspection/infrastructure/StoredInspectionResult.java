package com.factoryops.business.inspection.infrastructure;

public record StoredInspectionResult(String resultId, byte[] payloadHash) {
}
