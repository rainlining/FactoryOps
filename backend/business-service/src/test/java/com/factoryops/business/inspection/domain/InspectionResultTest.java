package com.factoryops.business.inspection.domain;

import static org.assertj.core.api.Assertions.assertThatThrownBy;

import java.math.BigDecimal;
import org.junit.jupiter.api.Test;

class InspectionResultTest {

    @Test
    void rejects_anomaly_decision_that_disagrees_with_score_and_threshold() {
        assertThatThrownBy(() -> InspectionResult.decision(false, new BigDecimal("0.8"), new BigDecimal("0.6")))
                .isInstanceOf(InconsistentAnomalyDecisionException.class);
    }

    @Test
    void treats_score_equal_to_threshold_as_anomaly() {
        InspectionResult.decision(true, new BigDecimal("0.6"), new BigDecimal("0.6"));
    }
}
