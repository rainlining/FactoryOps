package com.factoryops.business.batch.domain;

public class BatchCommandConflictException extends RuntimeException {
  public BatchCommandConflictException() {
    super("Batch already contains a different command");
  }
}
