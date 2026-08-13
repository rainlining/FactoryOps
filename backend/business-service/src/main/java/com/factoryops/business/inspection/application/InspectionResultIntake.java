package com.factoryops.business.inspection.application;

import tools.jackson.databind.JsonNode;

public interface InspectionResultIntake {
  IntakeOutcome accept(JsonNode payload);
}
