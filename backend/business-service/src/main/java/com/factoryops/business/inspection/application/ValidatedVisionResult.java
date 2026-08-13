package com.factoryops.business.inspection.application;

import java.math.BigDecimal;

public record ValidatedVisionResult(
    String inspectionId,
    String resultId,
    String originKind,
    String imageUri,
    String imageSha256,
    boolean anomaly,
    BigDecimal anomalyScore,
    BigDecimal decisionThreshold,
    byte[] canonicalPayload,
    byte[] payloadHash) {}
