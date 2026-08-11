package com.factoryops.business.inspection.application;

public final class VisionContractException extends RuntimeException {
    private final VisionContractIssue issue;

    public VisionContractException(VisionContractIssue issue) {
        super(issue.message());
        this.issue = issue;
    }

    public VisionContractIssue issue() {
        return issue;
    }
}
