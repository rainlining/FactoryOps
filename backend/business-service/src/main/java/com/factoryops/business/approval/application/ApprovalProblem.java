package com.factoryops.business.approval.application;

public final class ApprovalProblem extends RuntimeException {
  private final int status;
  private final String code;
  private final String path;

  public ApprovalProblem(int status, String code, String path, String message) {
    super(message);
    this.status = status;
    this.code = code;
    this.path = path;
  }

  public int status() { return status; }
  public String code() { return code; }
  public String path() { return path; }
}
