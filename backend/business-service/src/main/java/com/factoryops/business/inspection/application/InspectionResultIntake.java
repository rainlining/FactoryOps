package com.factoryops.business.inspection.application;

import tools.jackson.databind.JsonNode;

public interface InspectionResultIntake {
    IntakeDisposition accept(JsonNode payload);
}
