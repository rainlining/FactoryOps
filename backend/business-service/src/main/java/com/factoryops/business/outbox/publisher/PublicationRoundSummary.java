package com.factoryops.business.outbox.publisher;

public record PublicationRoundSummary(int selected, int published, int failed) {
  public static PublicationRoundSummary empty() {
    return new PublicationRoundSummary(0, 0, 0);
  }
}
