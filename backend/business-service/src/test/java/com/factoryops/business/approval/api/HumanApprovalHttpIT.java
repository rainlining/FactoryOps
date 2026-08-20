package com.factoryops.business.approval.api;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.*;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.*;

import com.factoryops.business.approval.application.HumanApprovalContractValidator;
import com.factoryops.business.approval.application.ApprovedBatchHoldExecutionService;
import java.nio.charset.StandardCharsets;
import java.time.Instant;
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
import tools.jackson.databind.json.JsonMapper;

@SpringBootTest(
    properties = {
      "factoryops.clock.fixed=2026-08-20T11:30:00Z",
      "factoryops.approval.service-token=test-agent-token",
      "factoryops.approval.authorized-actors=quality-lead:test-quality-token,production-lead:test-production-token"
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
  @Autowired JsonMapper mapper;
  @Autowired HumanApprovalContractValidator validator;
  @Autowired ApprovedBatchHoldExecutionService actionExecution;

  @BeforeEach
  void clean() {
    jdbc.update("DELETE FROM approved_action_executions");
    jdbc.update("DELETE FROM business_approval_history");
    jdbc.update("DELETE FROM business_approvals");
    jdbc.update("DELETE FROM quality_incidents WHERE incident_id=?", "QI-" + "5".repeat(64));
    jdbc.update("DELETE FROM vision_inspection_results WHERE result_id='RES-APPROVAL'");
    jdbc.update("DELETE FROM inspections WHERE inspection_id='INS-APPROVAL'");
    jdbc.update("DELETE FROM batches WHERE batch_id='BATCH-APPROVAL'");
    seedIncident();
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
  void create_requires_incident_bound_v11() throws Exception {
    create(pending().replace("\"1.1.0\"", "\"1.0.0\"")
            .replace(",\n    \"incident_id\": \"QI-5555555555555555555555555555555555555555555555555555555555555555\"", ""))
        .andExpect(status().isUnprocessableEntity());
    assertThat(count("business_approvals")).isZero();
  }

  @Test
  void create_rejects_unknown_incident_without_rows() throws Exception {
    create(pending().replace("QI-" + "5".repeat(64), "QI-" + "F".repeat(64)))
        .andExpect(status().isUnprocessableEntity())
        .andExpect(jsonPath("$.code").value("approval_incident_not_found"));
    assertThat(count("business_approvals")).isZero();
    assertThat(count("business_approval_history")).isZero();
  }

  @Test
  void reads_legacy_v10_without_incident_binding() throws Exception {
    var legacy = (tools.jackson.databind.node.ObjectNode) mapper.readTree(pending());
    legacy.put("contract_version", "1.0.0");
    ((tools.jackson.databind.node.ObjectNode) legacy.path("identity")).remove("incident_id");
    var value = validator.validate(legacy);
    var now = Instant.parse("2026-08-20T11:00:00Z");
    var text = new String(value.canonical(), StandardCharsets.UTF_8);
    jdbc.update(
        "INSERT INTO business_approvals (approval_id,approval_key,decision_id,decision_key,fusion_id,fusion_key,run_id,incident_id,coordinator_execution_id,fusion_round,proposed_action,risk_level,requested_at,expires_at,revision,status,canonical_sha256,payload,created_at,updated_at) VALUES (?,?,?,?,?,?,?,NULL,?,?,?,?,?,?,1,'PENDING',?,?,?,?)",
        value.approvalId(), value.approvalKey(), value.decisionId(), value.decisionKey(),
        value.fusionId(), value.fusionKey(), value.runId(), value.coordinatorExecutionId(),
        value.round(), value.proposedAction(), value.riskLevel(), value.requestedAt(),
        value.expiresAt(), value.sha256(), text, now, now);
    jdbc.update(
        "INSERT INTO business_approval_history (approval_id,revision,status,actor_id,canonical_sha256,payload,recorded_at) VALUES (?,1,'PENDING',NULL,?,?,?)",
        value.approvalId(), value.sha256(), text, now);
    mvc.perform(get("/api/v1/approvals/" + key()))
        .andExpect(status().isOk())
        .andExpect(jsonPath("$.approval.contract_version").value("1.0.0"))
        .andExpect(jsonPath("$.approval.identity.incident_id").doesNotExist());
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
    mvc.perform(
            post("/api/v1/approvals/" + key() + "/decision")
                .header("X-FactoryOps-Actor-Id", "quality-lead")
                .header("X-FactoryOps-Actor-Token", "wrong-token")
                .contentType("application/json")
                .content("{\"decision\":\"APPROVED\",\"reason_code\":\"PASS\"}"))
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
  void query_fails_closed_on_terminal_audit_projection_corruption() throws Exception {
    create(pending()).andExpect(status().isCreated());
    decide("quality-lead", "APPROVED", "MANUAL_REVIEW_PASSED").andExpect(status().isOk());
    jdbc.update("UPDATE business_approvals SET actor_id='different-actor'");
    mvc.perform(get("/api/v1/approvals/" + key()))
        .andExpect(status().isInternalServerError())
        .andExpect(jsonPath("$.code").value("approval_integrity_error"));
  }

  @Test
  void query_fails_closed_on_incident_projection_corruption() throws Exception {
    create(pending()).andExpect(status().isCreated());
    jdbc.update("UPDATE business_approvals SET incident_id='QI-" + "F".repeat(64) + "'");
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

  @Test
  void approved_hold_executes_resolved_batch_and_replays() throws Exception {
    create(holdPending()).andExpect(status().isCreated());
    decide("quality-lead", "APPROVED", "MANUAL_REVIEW_PASSED").andExpect(status().isOk());
    execute("{\"batch_id\":\"ATTACKER-BATCH\"}")
        .andExpect(status().isOk())
        .andExpect(jsonPath("$.batch_id").value("BATCH-APPROVAL"))
        .andExpect(jsonPath("$.replayed").value(false));
    execute("{}").andExpect(status().isOk()).andExpect(jsonPath("$.replayed").value(true));
    assertThat(jdbc.queryForObject("SELECT status FROM batches WHERE batch_id='BATCH-APPROVAL'", String.class))
        .isEqualTo("HELD");
    assertThat(count("approved_action_executions")).isEqualTo(1);
  }

  @Test
  void pending_or_unsupported_approval_has_no_side_effect() throws Exception {
    create(holdPending()).andExpect(status().isCreated());
    execute("{}").andExpect(status().isConflict()).andExpect(jsonPath("$.code").value("approval_not_approved"));
    assertThat(count("approved_action_executions")).isZero();
    assertThat(jdbc.queryForObject("SELECT status FROM batches WHERE batch_id='BATCH-APPROVAL'", String.class))
        .isEqualTo("OPEN");
  }

  @Test
  void approved_non_hold_action_is_rejected_without_side_effect() throws Exception {
    create(pending()).andExpect(status().isCreated());
    decide("quality-lead", "APPROVED", "MANUAL_REVIEW_PASSED").andExpect(status().isOk());
    execute("{}").andExpect(status().isUnprocessableEntity())
        .andExpect(jsonPath("$.code").value("approved_action_unsupported"));
    assertThat(count("approved_action_executions")).isZero();
    assertThat(jdbc.queryForObject("SELECT status FROM batches WHERE batch_id='BATCH-APPROVAL'", String.class))
        .isEqualTo("OPEN");
  }

  @Test
  void receipt_failure_rolls_back_batch_hold() throws Exception {
    create(holdPending()).andExpect(status().isCreated());
    decide("quality-lead", "APPROVED", "MANUAL_REVIEW_PASSED").andExpect(status().isOk());
    jdbc.execute("ALTER TABLE approved_action_executions ADD CONSTRAINT chk_injected_receipt_failure CHECK (approval_id <> 'APR-28BB1D59E0933638D81B8BB6F2F6EF91')");
    try {
      assertThatThrownBy(() -> actionExecution.execute(key())).isInstanceOf(RuntimeException.class);
    } finally {
      jdbc.execute("ALTER TABLE approved_action_executions DROP CHECK chk_injected_receipt_failure");
    }
    assertThat(count("approved_action_executions")).isZero();
    assertThat(jdbc.queryForObject("SELECT status FROM batches WHERE batch_id='BATCH-APPROVAL'", String.class))
        .isEqualTo("OPEN");
  }

  @Test
  void concurrent_identical_execution_has_one_receipt() throws Exception {
    create(holdPending()).andExpect(status().isCreated());
    decide("quality-lead", "APPROVED", "MANUAL_REVIEW_PASSED").andExpect(status().isOk());
    var start = new CountDownLatch(1);
    var pool = Executors.newFixedThreadPool(2);
    try {
      var first = pool.submit(() -> concurrentExecute(start));
      var second = pool.submit(() -> concurrentExecute(start));
      start.countDown();
      assertThat(java.util.List.of(first.get(), second.get()))
          .containsExactlyInAnyOrder(false, true);
    } finally {
      pool.shutdownNow();
    }
    assertThat(count("approved_action_executions")).isEqualTo(1);
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
            .header("X-FactoryOps-Actor-Token", actor.equals("quality-lead") ? "test-quality-token" : "test-production-token")
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

  private boolean concurrentExecute(CountDownLatch start) throws Exception {
    start.await();
    return mapper.readTree(execute("{}").andReturn().getResponse().getContentAsString())
        .path("replayed").asBoolean();
  }

  private org.springframework.test.web.servlet.ResultActions execute(String body) throws Exception {
    return mvc.perform(
        post("/internal/api/v1/approvals/" + key() + "/execute")
            .header("X-FactoryOps-Service-Token", "test-agent-token")
            .contentType("application/json")
            .content(body));
  }

  private int count(String table) {
    return jdbc.queryForObject("SELECT COUNT(*) FROM " + table, Integer.class);
  }

  private void seedIncident() {
    var now = Instant.parse("2026-08-20T10:00:00Z");
    jdbc.update(
        "INSERT IGNORE INTO batches (batch_id_hash,batch_id,kind,product_code,production_line,status,created_at) VALUES (UNHEX(SHA2('BATCH-APPROVAL',256)),'BATCH-APPROVAL','PRODUCTION','DEMO','LINE-1','OPEN',?)",
        now);
    jdbc.update(
        "INSERT IGNORE INTO inspections (inspection_id_hash,inspection_id,expected_image_uri,expected_image_sha256,status,created_at,completed_at,batch_id_hash,batch_id) VALUES (UNHEX(SHA2('INS-APPROVAL',256)),'INS-APPROVAL','artifact://approval','" + "A".repeat(64) + "','COMPLETED',?,?,UNHEX(SHA2('BATCH-APPROVAL',256)),'BATCH-APPROVAL')",
        now, now);
    jdbc.update(
        "INSERT IGNORE INTO vision_inspection_results (result_id_hash,result_id,inspection_id_hash,inspection_id,origin_kind,anomaly_score_text,decision_threshold_text,canonical_payload,payload_hash,created_at) VALUES (UNHEX(SHA2('RES-APPROVAL',256)),'RES-APPROVAL',UNHEX(SHA2('INS-APPROVAL',256)),'INS-APPROVAL','recorded','1','0.5','{}',UNHEX(SHA2('{}',256)),?)",
        now);
    var incident = "QI-" + "5".repeat(64);
    jdbc.update(
        "INSERT IGNORE INTO quality_incidents (incident_id_hash,incident_id,incident_schema_version,status,batch_id_hash,batch_id,inspection_id_hash,inspection_id,result_id_hash,result_id,created_at) VALUES (UNHEX(SHA2(?,256)),?,'1.0','OPEN',UNHEX(SHA2('BATCH-APPROVAL',256)),'BATCH-APPROVAL',UNHEX(SHA2('INS-APPROVAL',256)),'INS-APPROVAL',UNHEX(SHA2('RES-APPROVAL',256)),'RES-APPROVAL',?)",
        incident, incident, now);
  }

  private String pending() throws Exception {
    try (var input = getClass().getResourceAsStream("/fixtures/human-approval-pending.json")) {
      return new String(
          Objects.requireNonNull(input).readAllBytes(), StandardCharsets.UTF_8);
    }
  }

  private String holdPending() throws Exception {
    return pending().replace("STOP_LINE", "HOLD_BATCH");
  }

  private String key() {
    return "APK-28BB1D59E0933638D81B8BB6F2F6EF91DA8C03BC7BA0D7E3E61A8D1B157E3B97";
  }
}
