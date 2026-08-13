package com.factoryops.business.inspection.application;

public record IntakeOutcome(IntakeDisposition disposition, String incidentId) {
  public String name() {
    return disposition.name();
  }
}
