package com.factoryops.business.inspection.application;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;

import java.io.InputStream;
import org.junit.jupiter.api.Test;
import tools.jackson.databind.JsonNode;
import tools.jackson.databind.json.JsonMapper;

class VisionInspectionContractValidatorTest {
    private final JsonMapper mapper = JsonMapper.builder().build();
    private final VisionInspectionContractValidator validator = new VisionInspectionContractValidator(mapper);

    @Test
    void accepts_shared_valid_fixture() throws Exception {
        assertThat(validator.validate(fixture("valid/fake-result.json")).resultId())
                .isEqualTo("result-fake-0001");
    }

    @Test
    void reports_score_range_at_stable_path() throws Exception {
        assertThatThrownBy(() -> validator.validate(fixture("invalid/anomaly-score-out-of-range.json")))
                .isInstanceOfSatisfying(VisionContractException.class, error -> {
                    assertThat(error.issue().code()).isEqualTo("maximum");
                    assertThat(error.issue().path()).isEqualTo("$.observation.anomaly_score");
                });
    }

    @Test
    void reports_domain_contradiction_after_schema_validation() throws Exception {
        assertThatThrownBy(() -> validator.validate(fixture("invalid/anomaly-decision-conflict.json")))
                .isInstanceOfSatisfying(VisionContractException.class, error ->
                        assertThat(error.issue().code()).isEqualTo("inconsistent_anomaly_decision"));
    }

    private JsonNode fixture(String name) throws Exception {
        try (InputStream input = getClass().getResourceAsStream("/fixtures/" + name)) {
            return mapper.readTree(input);
        }
    }
}
