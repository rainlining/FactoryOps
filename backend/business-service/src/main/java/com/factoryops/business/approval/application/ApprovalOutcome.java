package com.factoryops.business.approval.application;

import tools.jackson.databind.JsonNode;

public record ApprovalOutcome(JsonNode approval, boolean replayed) {}
