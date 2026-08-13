package com.factoryops.business.inspection.domain;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;

import java.time.Instant;
import org.junit.jupiter.api.Test;

class InspectionTest {
  private final InspectionInput input = new InspectionInput("artifact://images/a", "a".repeat(64));

  @Test
  void completes_once_and_keeps_first_time() {
    var inspection =
        Inspection.pending("i-1", "B-TEST", input, Instant.parse("2026-08-13T00:00:00Z"));
    var first = Instant.parse("2026-08-13T01:00:00Z");
    inspection.complete(first);
    inspection.complete(Instant.parse("2026-08-13T02:00:00Z"));
    assertThat(inspection.status()).isEqualTo(InspectionStatus.COMPLETED);
    assertThat(inspection.completedAt()).isEqualTo(first);
  }

  @Test
  void identifies_the_first_input_mismatch() {
    assertThat(input.firstMismatch(new InspectionInput("artifact://images/b", "b".repeat(64))))
        .contains("$.input.image_uri");
  }

  @Test
  void rejects_invalid_sha256() {
    assertThatThrownBy(() -> new InspectionInput("artifact://images/a", "ABC"))
        .isInstanceOf(IllegalArgumentException.class);
  }
}
