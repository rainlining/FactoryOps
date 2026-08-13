package com.factoryops.business.batch.application;

public class HoldEvidenceException extends RuntimeException {
  private final String code;

  public HoldEvidenceException(String c) {
    code = c;
  }

  public String code() {
    return code;
  }
}
