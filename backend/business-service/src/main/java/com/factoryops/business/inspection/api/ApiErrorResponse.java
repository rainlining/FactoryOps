package com.factoryops.business.inspection.api;

public record ApiErrorResponse(String code, String path, String message) {
}
