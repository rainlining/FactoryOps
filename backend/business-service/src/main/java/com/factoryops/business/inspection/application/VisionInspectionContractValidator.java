package com.factoryops.business.inspection.application;

import com.factoryops.business.inspection.domain.InconsistentAnomalyDecisionException;
import com.factoryops.business.inspection.domain.InspectionResult;
import com.networknt.schema.Schema;
import com.networknt.schema.SchemaRegistry;
import com.networknt.schema.SpecificationVersion;
import java.io.IOException;
import java.util.Comparator;
import tools.jackson.databind.JsonNode;
import tools.jackson.databind.json.JsonMapper;

public final class VisionInspectionContractValidator {
    private final Schema schema;

    public VisionInspectionContractValidator(JsonMapper mapper) {
        try (var input = getClass().getResourceAsStream("/contracts/vision_inspection/v1.0/schema.json")) {
            if (input == null) throw new IllegalStateException("Vision schema is missing from classpath");
            this.schema = SchemaRegistry.withDefaultDialect(SpecificationVersion.DRAFT_2020_12)
                    .getSchema(mapper.readTree(input));
        } catch (IOException error) {
            throw new IllegalStateException("Cannot load Vision schema", error);
        }
    }

    public ValidatedVisionResult validate(JsonNode payload) {
        var version = payload.path("contract_version").asText("");
        if (!"1.0".equals(version)) {
            throw issue("unsupported_contract_version", "$.contract_version", "Only contract_version 1.0 is supported");
        }
        var errors = schema.validate(payload);
        if (!errors.isEmpty()) {
            var first = errors.stream()
                    .min(Comparator.comparing(error -> error.getInstanceLocation().toString()))
                    .orElseThrow();
            throw issue(first.getKeyword(), jsonPath(first.getInstanceLocation().toString()), first.getMessage());
        }
        var observation = payload.get("observation");
        var score = observation.get("anomaly_score").decimalValue();
        var threshold = observation.get("decision_threshold").decimalValue();
        try {
            InspectionResult.decision(observation.get("is_anomaly").booleanValue(), score, threshold);
        } catch (InconsistentAnomalyDecisionException error) {
            throw issue("inconsistent_anomaly_decision", "$.observation.is_anomaly", error.getMessage());
        }
        var canonical = CanonicalJson.canonicalize(payload);
        return new ValidatedVisionResult(
                payload.get("inspection_id").asText(), payload.get("result_id").asText(),
                payload.get("origin").get("kind").asText(), score, threshold,
                canonical, CanonicalJson.sha256(payload));
    }

    private static VisionContractException issue(String code, String path, String message) {
        return new VisionContractException(new VisionContractIssue(code, path, message));
    }

    private static String jsonPath(String pointer) {
        if (pointer.isEmpty()) return "$";
        var path = new StringBuilder("$");
        for (var segment : pointer.substring(1).split("/")) {
            path.append('.').append(segment.replace("~1", "/").replace("~0", "~"));
        }
        return path.toString();
    }
}
