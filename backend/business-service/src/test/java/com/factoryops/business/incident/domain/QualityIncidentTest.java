package com.factoryops.business.incident.domain;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;

import java.time.Instant;
import org.junit.jupiter.api.Test;

class QualityIncidentTest {
  @Test
  void derives_stable_namespaced_id() {
    assertThat(QualityIncidentId.fromResultId("result-1"))
        .isEqualTo(QualityIncidentId.fromResultId("result-1"))
        .startsWith("QI-")
        .hasSize(67);
    assertThat(QualityIncidentId.fromResultId("result-2"))
        .isNotEqualTo(QualityIncidentId.fromResultId("result-1"));
  }

  @Test
  void opens_versioned_incident_with_required_evidence() {
    var incident = QualityIncident.open("B-1", "inspection-1", "result-1", Instant.EPOCH);
    assertThat(incident.schemaVersion()).isEqualTo("1.0");
    assertThat(incident.status()).isEqualTo("OPEN");
    assertThatThrownBy(() -> QualityIncident.open("", "inspection-1", "result-1", Instant.EPOCH))
        .isInstanceOf(IllegalArgumentException.class);
  }
}
