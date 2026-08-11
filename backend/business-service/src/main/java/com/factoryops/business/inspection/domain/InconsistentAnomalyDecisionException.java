package com.factoryops.business.inspection.domain;

public final class InconsistentAnomalyDecisionException extends IllegalArgumentException {
    public InconsistentAnomalyDecisionException() {
        super("is_anomaly must equal anomaly_score >= decision_threshold");
    }
}
