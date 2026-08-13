package com.factoryops.business.batch.api;

import static org.assertj.core.api.Assertions.assertThat;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.*;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.*;

import com.factoryops.business.batch.application.BatchApplicationService;
import com.factoryops.business.batch.domain.*;
import java.util.*;
import java.util.concurrent.*;
import org.junit.jupiter.api.*;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.boot.webmvc.test.autoconfigure.AutoConfigureMockMvc;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.test.context.*;
import org.springframework.test.web.servlet.MockMvc;
import org.testcontainers.junit.jupiter.*;
import org.testcontainers.mysql.MySQLContainer;

@SpringBootTest(properties = "factoryops.clock.fixed=2026-08-13T08:00:00Z")
@AutoConfigureMockMvc
@Testcontainers
class BatchLifecycleHttpIT {
  @Container static final MySQLContainer MYSQL = new MySQLContainer("mysql:8.4");

  @DynamicPropertySource
  static void mysql(DynamicPropertyRegistry r) {
    r.add("spring.datasource.url", MYSQL::getJdbcUrl);
    r.add("spring.datasource.username", MYSQL::getUsername);
    r.add("spring.datasource.password", MYSQL::getPassword);
  }

  @Autowired MockMvc mvc;
  @Autowired JdbcTemplate jdbc;
  @Autowired BatchApplicationService service;

  @BeforeEach
  void clean() {
    jdbc.execute("SET FOREIGN_KEY_CHECKS=0");
    try {
      jdbc.update("DELETE FROM quality_incidents");
      jdbc.update("DELETE FROM vision_inspection_results");
      jdbc.update("DELETE FROM inspections");
      jdbc.update("DELETE FROM batches WHERE kind='PRODUCTION'");
    } finally {
      jdbc.execute("SET FOREIGN_KEY_CHECKS=1");
    }
  }

  @Test
  void creates_replays_conflicts_and_queries() throws Exception {
    var body = "{\"batch_id\":\"B-17\",\"product_code\":\"P-1\",\"production_line\":\"LINE-2\"}";
    mvc.perform(post("/api/v1/batches").contentType("application/json").content(body))
        .andExpect(status().isCreated())
        .andExpect(jsonPath("$.status").value("OPEN"));
    mvc.perform(post("/api/v1/batches").contentType("application/json").content(body))
        .andExpect(status().isOk())
        .andExpect(jsonPath("$.replayed").value(true));
    mvc.perform(get("/api/v1/batches/B-17"))
        .andExpect(status().isOk())
        .andExpect(jsonPath("$.inspection_count").value(0));
    mvc.perform(
            post("/api/v1/batches")
                .contentType("application/json")
                .content(body.replace("P-1", "P-2")))
        .andExpect(status().isConflict());
  }

  @Test
  void query_reports_inspection_count_for_batch() throws Exception {
    service.create("B-17", "P-1", "LINE-2");
    var first = inspectionRequest("inspection-1", "B-17", "artifact://images/a", "a");
    var second = inspectionRequest("inspection-2", "B-17", "artifact://images/b", "b");
    mvc.perform(post("/api/v1/inspections").contentType("application/json").content(first))
        .andExpect(status().isCreated());
    mvc.perform(get("/api/v1/batches/B-17"))
        .andExpect(status().isOk())
        .andExpect(jsonPath("$.inspection_count").value(1));
    mvc.perform(post("/api/v1/inspections").contentType("application/json").content(second))
        .andExpect(status().isCreated());
    mvc.perform(get("/api/v1/batches/B-17"))
        .andExpect(status().isOk())
        .andExpect(jsonPath("$.inspection_count").value(2));
  }

  @Test
  void holds_and_replays_same_command() throws Exception {
    service.create("B-17", "P-1", "LINE-2");
    var body = "{\"reason_code\":\"PROCESS_ANOMALY\",\"reason_detail\":\" pressure \"}";
    mvc.perform(post("/api/v1/batches/B-17/hold").contentType("application/json").content(body))
        .andExpect(status().isOk())
        .andExpect(jsonPath("$.replayed").value(false));
    mvc.perform(post("/api/v1/batches/B-17/hold").contentType("application/json").content(body))
        .andExpect(status().isOk())
        .andExpect(jsonPath("$.replayed").value(true));
  }

  @Test
  void legacy_is_queryable_but_not_actionable() throws Exception {
    mvc.perform(get("/api/v1/batches/SYS-LEGACY-UNASSIGNED"))
        .andExpect(status().isOk())
        .andExpect(jsonPath("$.kind").value("LEGACY_UNASSIGNED"));
    mvc.perform(
            post("/api/v1/batches/SYS-LEGACY-UNASSIGNED/hold")
                .contentType("application/json")
                .content("{\"reason_code\":\"PROCESS_ANOMALY\"}"))
        .andExpect(status().isConflict())
        .andExpect(jsonPath("$.code").value("batch_not_actionable"));
  }

  @Test
  void rejects_invalid_batch_requests_with_stable_codes() throws Exception {
    mvc.perform(
            post("/api/v1/batches")
                .contentType("application/json")
                .content(
                    "{\"batch_id\":\"lower\",\"product_code\":\"P-1\",\"production_line\":\"LINE-1\"}"))
        .andExpect(status().isUnprocessableEntity())
        .andExpect(jsonPath("$.code").value("invalid_batch_id"));
    mvc.perform(
            post("/api/v1/batches")
                .contentType("application/json")
                .content(
                    "{\"batch_id\":\"SYS-NEW\",\"product_code\":\"P-1\",\"production_line\":\"LINE-1\"}"))
        .andExpect(status().isUnprocessableEntity())
        .andExpect(jsonPath("$.code").value("reserved_batch_id"));
    service.create("B-17", "P-1", "LINE-2");
    mvc.perform(
            post("/api/v1/batches/B-17/hold")
                .contentType("application/json")
                .content("{\"reason_code\":\"UNKNOWN\"}"))
        .andExpect(status().isUnprocessableEntity())
        .andExpect(jsonPath("$.code").value("invalid_hold_command"));
  }

  @Test
  void anomaly_evidence_holds_batch_and_non_anomaly_rolls_back() throws Exception {
    service.create("B-17", "P-1", "LINE-2");
    var anomaly = fixture("valid/vision-service-result.json");
    mvc.perform(
            post("/api/v1/inspections")
                .contentType("application/json")
                .content(
                    "{\"inspection_id\":\"inspection-00731\",\"batch_id\":\"B-17\",\"input\":{\"image_uri\":\"artifact://images/sheet-metal-00731\",\"sha256\":\""
                        + "a".repeat(64)
                        + "\"}}"))
        .andExpect(status().isCreated());
    mvc.perform(post("/api/v1/inspection-results").contentType("application/json").content(anomaly))
        .andExpect(status().isCreated());
    mvc.perform(
            post("/api/v1/batches/B-17/hold")
                .contentType("application/json")
                .content(
                    "{\"reason_code\":\"QUALITY_ANOMALY\",\"inspection_id\":\"inspection-00731\",\"result_id\":\"result-1001\"}"))
        .andExpect(status().isOk())
        .andExpect(jsonPath("$.status").value("HELD"));
    service.create("B-18", "P-1", "LINE-2");
    mvc.perform(
            post("/api/v1/batches/B-18/hold")
                .contentType("application/json")
                .content(
                    "{\"reason_code\":\"QUALITY_ANOMALY\",\"inspection_id\":\"inspection-00731\",\"result_id\":\"result-1001\"}"))
        .andExpect(status().isUnprocessableEntity())
        .andExpect(jsonPath("$.code").value("hold_evidence_mismatch"));
    assertThat(
            jdbc.queryForObject("SELECT status FROM batches WHERE batch_id='B-18'", String.class))
        .isEqualTo("OPEN");
  }

  @Test
  void released_batch_rejects_new_inspection_but_accepts_original_replay() throws Exception {
    service.create("B-17", "P-1", "LINE-2");
    var inspection =
        "{\"inspection_id\":\"inspection-1\",\"batch_id\":\"B-17\",\"input\":{\"image_uri\":\"artifact://images/a\",\"sha256\":\""
            + "a".repeat(64)
            + "\"}}";
    mvc.perform(post("/api/v1/inspections").contentType("application/json").content(inspection))
        .andExpect(status().isCreated());
    service.hold("B-17", HoldCommand.manual(HoldReasonCode.PROCESS_ANOMALY, "x"));
    service.release("B-17", ReleaseCommand.external(ReleaseReasonCode.RECHECK_PASSED, "ok"));
    mvc.perform(post("/api/v1/inspections").contentType("application/json").content(inspection))
        .andExpect(status().isOk())
        .andExpect(jsonPath("$.replayed").value(true));
    mvc.perform(
            post("/api/v1/inspections")
                .contentType("application/json")
                .content(inspection.replace("inspection-1", "inspection-2")))
        .andExpect(status().isConflict())
        .andExpect(jsonPath("$.code").value("batch_not_accepting_inspections"));
  }

  @Test
  void internal_release_is_terminal_and_has_no_http_route() throws Exception {
    service.create("B-17", "P-1", "LINE-2");
    service.hold("B-17", HoldCommand.manual(HoldReasonCode.PROCESS_ANOMALY, "x"));
    var command = ReleaseCommand.external(ReleaseReasonCode.RECHECK_PASSED, "ok");
    assertThat(service.release("B-17", command).replayed()).isFalse();
    assertThat(service.release("B-17", command).replayed()).isTrue();
    mvc.perform(post("/api/v1/batches/B-17/release").contentType("application/json").content("{}"))
        .andExpect(status().isNotFound());
  }

  @Test
  void concurrent_different_holds_keep_one_winner() {
    service.create("B-17", "P-1", "LINE-2");
    var start = new CountDownLatch(1);
    var ex = Executors.newFixedThreadPool(2);
    try {
      var fs =
          List.of(
              ex.submit(() -> outcome(start, HoldReasonCode.PROCESS_ANOMALY)),
              ex.submit(() -> outcome(start, HoldReasonCode.MANUAL_QUALITY_HOLD)));
      start.countDown();
      assertThat(fs).extracting(f -> f.get()).containsExactlyInAnyOrder("APPLIED", "CONFLICT");
    } catch (Exception e) {
      throw new RuntimeException(e);
    } finally {
      ex.shutdownNow();
    }
  }

  @Test
  void concurrent_identical_batch_creates_one_row() {
    var start = new CountDownLatch(1);
    var ex = Executors.newFixedThreadPool(2);
    try {
      var fs =
          List.of(
              ex.submit(
                  () -> {
                    start.await();
                    return service.create("B-17", "P-1", "LINE-2").replayed();
                  }),
              ex.submit(
                  () -> {
                    start.await();
                    return service.create("B-17", "P-1", "LINE-2").replayed();
                  }));
      start.countDown();
      assertThat(fs).extracting(f -> f.get()).containsExactlyInAnyOrder(false, true);
      assertThat(
              jdbc.queryForObject(
                  "SELECT COUNT(*) FROM batches WHERE batch_id='B-17'", Integer.class))
          .isEqualTo(1);
    } catch (Exception e) {
      throw new RuntimeException(e);
    } finally {
      ex.shutdownNow();
    }
  }

  private String outcome(CountDownLatch s, HoldReasonCode c) throws Exception {
    s.await();
    try {
      return service.hold("B-17", HoldCommand.manual(c, "x")).replayed() ? "REPLAY" : "APPLIED";
    } catch (BatchCommandConflictException e) {
      return "CONFLICT";
    }
  }

  private String fixture(String name) throws Exception {
    try (var input = getClass().getResourceAsStream("/fixtures/" + name)) {
      return new String(
          Objects.requireNonNull(input).readAllBytes(), java.nio.charset.StandardCharsets.UTF_8);
    }
  }

  private String inspectionRequest(String id, String batchId, String uri, String shaPrefix) {
    return "{\"inspection_id\":\""
        + id
        + "\",\"batch_id\":\""
        + batchId
        + "\",\"input\":{\"image_uri\":\""
        + uri
        + "\",\"sha256\":\""
        + shaPrefix.repeat(64)
        + "\"}}";
  }
}
