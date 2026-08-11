package com.factoryops.business.inspection.application;

public final class ResultIdentityConflictException extends RuntimeException {
    public ResultIdentityConflictException(String resultId) {
        super("result_id already identifies different content: " + resultId);
    }
}
