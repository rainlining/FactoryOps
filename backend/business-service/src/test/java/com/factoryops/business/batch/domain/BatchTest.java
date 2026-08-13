package com.factoryops.business.batch.domain;

import static org.assertj.core.api.Assertions.*;

import java.time.Instant;
import org.junit.jupiter.api.Test;

class BatchTest {
  private static final Instant T = Instant.parse("2026-08-13T08:00:00Z");

  @Test
  void production_starts_open_and_holds_once() {
    var b = Batch.production("B-17", "SHEET-METAL-A", "LINE-2", T);
    var c = HoldCommand.manual(HoldReasonCode.PROCESS_ANOMALY, " pressure ");
    assertThat(b.hold(c, T)).isEqualTo(CommandDisposition.APPLIED);
    assertThat(b.hold(c, T.plusSeconds(1))).isEqualTo(CommandDisposition.REPLAYED);
    assertThat(b.heldAt()).isEqualTo(T);
  }

  @Test
  void conflicting_hold_and_invalid_release_are_rejected() {
    var b = Batch.production("B-17", "P-1", "LINE-2", T);
    assertThatThrownBy(
            () -> b.release(new ReleaseCommand(ReleaseReasonCode.RECHECK_PASSED, "ok"), T))
        .isInstanceOf(InvalidBatchTransitionException.class);
    b.hold(HoldCommand.manual(HoldReasonCode.PROCESS_ANOMALY, "x"), T);
    assertThatThrownBy(() -> b.hold(HoldCommand.manual(HoldReasonCode.MANUAL_QUALITY_HOLD, "x"), T))
        .isInstanceOf(BatchCommandConflictException.class);
  }

  @Test
  void quality_reason_requires_evidence_and_identifiers_are_strict() {
    assertThatThrownBy(() -> HoldCommand.manual(HoldReasonCode.QUALITY_ANOMALY, "x"))
        .isInstanceOf(IllegalArgumentException.class);
    assertThatThrownBy(() -> Batch.production("b-17", "P-1", "LINE-2", T))
        .isInstanceOf(IllegalArgumentException.class);
    assertThatThrownBy(() -> Batch.production("SYS-X", "P-1", "LINE-2", T))
        .isInstanceOf(IllegalArgumentException.class);
  }
}
