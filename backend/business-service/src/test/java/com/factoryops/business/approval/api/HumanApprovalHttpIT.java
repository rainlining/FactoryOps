package com.factoryops.business.approval.api;

import static org.assertj.core.api.Assertions.assertThat;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.*;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.*;

import java.nio.charset.StandardCharsets;
import java.util.Objects;
import java.util.concurrent.CountDownLatch;
import java.util.concurrent.Executors;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.boot.webmvc.test.autoconfigure.AutoConfigureMockMvc;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.test.context.DynamicPropertyRegistry;
import org.springframework.test.context.DynamicPropertySource;
import org.springframework.test.web.servlet.MockMvc;
import org.testcontainers.junit.jupiter.Container;
import org.testcontainers.junit.jupiter.Testcontainers;
import org.testcontainers.mysql.MySQLContainer;

@SpringBootTest(
    properties = {
      "factoryops.clock.fixed=2026-08-20T11:30:00Z",
      "factoryops.approval.service-token=test-agent-token",
      "factoryops.approval.authorized-actors=quality-lead,production-lead"
    })
@AutoConfigureMockMvc
@Testcontainers
class HumanApprovalHttpIT {
  @Container static final MySQLContainer MYSQL = new MySQLContainer("mysql:8.4");

  @DynamicPropertySource
  static void mysql(DynamicPropertyRegistry registry) {
    registry.add("spring.datasource.url", MYSQL::getJdbcUrl);
    registry.add("spring.datasource.username", MYSQL::getUsername);
    registry.add("spring.datasource.password", MYSQL::getPassword);
  }

  @Autowired MockMvc mvc;
  @Autowired JdbcTemplate jdbc;

  @BeforeEach
  void clean() {
    jdbc.update("DELETE FROM business_approval_history");
    jdbc.update("DELETE FROM business_approvals");
  }

  @Test
  void creates_replays_queries_and_rejects_conflict() throws Exception {
    var pending = pending();
    create(pending).andExpect(status().isCreated()).andExpect(jsonPath("$.replayed").value(false));
    create(pending).andExpect(status().isOk()).andExpect(jsonPath("$.replayed").value(true));
    mvc.perform(get("/api/v1/approvals/" + key()))
        .andExpect(status().isOk())
        .andExpect(jsonPath("$.approval.state.status").value("PENDING"));
    create(pending.replace("HIGH_RISK_ACTION", "POLICY_OVERRIDE"))
        .andExpect(status().isConflict())
        .andExpect(jsonPath("$.code").value("approval_identity_conflict"));
    assertThat(count("business_approvals")).isEqualTo(1);
    assertThat(count("business_approval_history")).isEqualTo(1);
  }

  @Test
  void create_requires_service_token_and_pending_contract() throws Exception {
    mvc.perform(post("/internal/api/v1/approvals").contentType("application/json").content(pending()))
        .andExpect(status().isForbidden());
    create(pending().replace("\"PENDING\"", "\"APPROVED\""))
        .andExpect(status().isUnprocessableEntity());
    assertThat(count("business_approvals")).isZero();
  }

  @Test
  void authorized_actor_decides_and_identical_command_replays() throws Exception {
    create(pending()).andExpect(status().isCreated());
    decide("quality-lead", "APPROVED", "MANUAL_REVIEW_PASSED")
        .andExpect(status().isOk())
        .andExpect(jsonPath("$.replayed").value(false))
        .andExpect(jsonPath("$.approval.state.status").value("APPROVED"));
    decide("quality-lead", "APPROVED", "MANUAL_REVIEW_PASSED")
        .andExpect(status().isOk())
        .andExpect(jsonPath("$.replayed").value(true));
    decide("production-lead", "REJECTED", "UNSAFE_TO_EXECUTE")
        .andExpect(status().isConflict());
    assertThat(count("business_approval_history")).isEqualTo(2);
  }

  @Test
  void unknown_actor_is_forbidden_without_mutation() throws Exception {
    create(pending()).andExpect(status().isCreated());
    decide("intruder", "APPROVED", "MANUAL_REVIEW_PASSED")
        .andExpect(status().isForbidden());
    assertThat(jdbc.queryForObject("SELECT status FROM business_approvals", String.class))
        .isEqualTo("PENDING");
    assertThat(count("business_approval_history")).isEqualTo(1);
  }

  @Test
  void expiry_boundary_rejects_human_decision() throws Exception {
    create(pending().replace("2026-08-20T12:00:00Z", "2026-08-20T11:30:00Z"))
        .andExpect(status().isCreated());
    decide("quality-lead", "APPROVED", "MANUAL_REVIEW_PASSED")
        .andExpect(status().isConflict())
        .andExpect(jsonPath("$.code").value("approval_window_expired"));
    assertThat(count("business_approval_history")).isEqualTo(1);
  }

  @Test
  void query_fails_closed_on_history_corruption() throws Exception {
    create(pending()).andExpect(status().isCreated());
    jdbc.update("UPDATE business_approval_history SET canonical_sha256=UNHEX(REPEAT('00',32))");
    mvc.perform(get("/api/v1/approvals/" + key()))
        .andExpect(status().isInternalServerError())
        .andExpect(jsonPath("$.code").value("approval_integrity_error"));
  }

  @Test
  void concurrent_opposite_decisions_have_one_winner() throws Exception {
    create(pending()).andExpect(status().isCreated());
    var unrelatedBefore =
        jdbc.queryForObject("SELECT COUNT(*) FROM batches WHERE status <> 'OPEN'", Integer.class);
    var start = new CountDownLatch(1);
    var pool = Executors.newFixedThreadPool(2);
    try {
      var approved = pool.submit(() -> concurrentDecision(start, "APPROVED", "PASS"));
      var rejected = pool.submit(() -> concurrentDecision(start, "REJECTED", "FAIL"));
      start.countDown();
      assertThat(java.util.List.of(approved.get(), rejected.get()))
          .containsExactlyInAnyOrder(200, 409);
    } finally {
      pool.shutdownNow();
    }
    assertThat(count("business_approval_history")).isEqualTo(2);
    assertThat(jdbc.queryForObject("SELECT COUNT(*) FROM batches WHERE status <> 'OPEN'", Integer.class))
        .isEqualTo(unrelatedBefore);
  }

  private org.springframework.test.web.servlet.ResultActions create(String payload) throws Exception {
    return mvc.perform(
        post("/internal/api/v1/approvals")
            .header("X-FactoryOps-Service-Token", "test-agent-token")
            .contentType("application/json")
            .content(payload));
  }

  private org.springframework.test.web.servlet.ResultActions decide(
      String actor, String decision, String reason) throws Exception {
    return mvc.perform(
        post("/api/v1/approvals/" + key() + "/decision")
            .header("X-FactoryOps-Actor-Id", actor)
            .contentType("application/json")
            .content(
                "{\"decision\":\""
                    + decision
                    + "\",\"reason_code\":\""
                    + reason
                    + "\"}"));
  }

  private int concurrentDecision(CountDownLatch start, String decision, String reason)
      throws Exception {
    start.await();
    return decide("quality-lead", decision, reason).andReturn().getResponse().getStatus();
  }

  private int count(String table) {
    return jdbc.queryForObject("SELECT COUNT(*) FROM " + table, Integer.class);
  }

  private String pending() throws Exception {
    try (var input = getClass().getResourceAsStream("/fixtures/human-approval-pending.json")) {
      return new String(
          Objects.requireNonNull(input).readAllBytes(), StandardCharsets.UTF_8);
    }
  }

  private String key() {
    return "APK-28BB1D59E0933638D81B8BB6F2F6EF91DA8C03BC7BA0D7E3E61A8D1B157E3B97";
  }
}
