package com.factoryops.business.outbox.publisher;

public record PublicationRoundSummary(
    int selected, int published, int failed, Long lastSuccessfulOffset) {
  public PublicationRoundSummary(int selected, int published, int failed) {
    this(selected, published, failed, null);
  }

  public static PublicationRoundSummary empty() {
    return new PublicationRoundSummary(0, 0, 0, null);
  }
}
