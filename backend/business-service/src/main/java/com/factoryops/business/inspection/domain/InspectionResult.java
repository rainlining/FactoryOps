package com.factoryops.business.inspection.domain;

import java.math.BigDecimal;

public final class InspectionResult {
    private InspectionResult() {
    }

    public static void decision(boolean anomaly, BigDecimal score, BigDecimal threshold) {
        boolean derived = score.compareTo(threshold) >= 0;
        if (anomaly != derived) {
            throw new InconsistentAnomalyDecisionException();
        }
    }
}
