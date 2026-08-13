package com.factoryops.business.batch.api;

final class BatchRequestException extends RuntimeException {
    private final String code;
    private final String path;

    BatchRequestException(String code, String path, String message) {
        super(message);
        this.code = code;
        this.path = path;
    }

    String code() { return code; }
    String path() { return path; }
}
