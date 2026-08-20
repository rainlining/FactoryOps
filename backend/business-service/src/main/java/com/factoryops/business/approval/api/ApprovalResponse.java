package com.factoryops.business.approval.api;

import tools.jackson.databind.JsonNode;

public record ApprovalResponse(JsonNode approval, boolean replayed) {}
