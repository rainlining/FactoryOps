package com.factoryops.business.approval.application;

import java.nio.charset.StandardCharsets;
import java.time.Clock;
import java.time.Instant;
import java.time.ZoneOffset;
import java.time.format.DateTimeFormatter;
import java.time.temporal.ChronoUnit;
import java.util.Arrays;
import java.util.Map;
import org.springframework.beans.factory.annotation.Qualifier;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.stereotype.Service;
import org.springframework.transaction.support.TransactionTemplate;
import tools.jackson.databind.JsonNode;
import tools.jackson.databind.json.JsonMapper;
import tools.jackson.databind.node.ObjectNode;

@Service
public final class HumanApprovalApplicationService {
  private static final DateTimeFormatter UTC_MICROS =
      DateTimeFormatter.ofPattern("uuuu-MM-dd'T'HH:mm:ss.SSSSSS'Z'").withZone(ZoneOffset.UTC);
  private final JdbcTemplate jdbc;
  private final TransactionTemplate write;
  private final TransactionTemplate read;
  private final HumanApprovalContractValidator validator;
  private final JsonMapper mapper;
  private final Clock clock;

  public HumanApprovalApplicationService(
      JdbcTemplate jdbc,
      @Qualifier("inspectionWriteTransaction") TransactionTemplate write,
      @Qualifier("inspectionReadTransaction") TransactionTemplate read,
      HumanApprovalContractValidator validator,
      JsonMapper mapper,
      Clock clock) {
    this.jdbc = jdbc;
    this.write = write;
    this.read = read;
    this.validator = validator;
    this.mapper = mapper;
    this.clock = clock;
  }

  public ApprovalOutcome create(JsonNode input) {
    var candidate = validator.validate(input);
    if (!"1.1.0".equals(candidate.contractVersion()))
      throw problem(422, "approval_incident_binding_required", "$.contract_version", "Creation requires incident-bound Human Approval v1.1.0");
    if (!"PENDING".equals(candidate.status()) || candidate.revision() != 1)
      throw problem(422, "approval_must_be_pending", "$.state.status", "Creation accepts only revision 1 PENDING");
    return write.execute(status -> {
      var incidents = jdbc.queryForList(
          "SELECT incident_id FROM quality_incidents WHERE incident_id_hash=UNHEX(SHA2(?,256)) AND incident_id=? FOR SHARE",
          candidate.incidentId(), candidate.incidentId());
      if (incidents.size() != 1)
        throw problem(422, "approval_incident_not_found", "$.identity.incident_id", "Business Incident does not exist");
      var inserted = insertCurrent(candidate);
      var stored = findForUpdate(candidate.approvalKey(), candidate.approvalId());
      if (stored == null) throw new IllegalStateException("approval insert was not observable");
      requireIdentity(stored, candidate);
      var replay = !inserted;
      if (replay && !Arrays.equals((byte[]) stored.get("canonical_sha256"), candidate.sha256()))
        throw problem(409, "approval_identity_conflict", "$.identity.approval_key", "Approval identity already contains different facts");
      if (inserted) insertHistory(candidate, clock.instant());
      return new ApprovalOutcome(candidate.payload(), replay);
    });
  }

  public ApprovalOutcome decide(String key, String actor, String decision, String reason, String comment) {
    if (!("APPROVED".equals(decision) || "REJECTED".equals(decision)))
      throw problem(422, "approval_decision_invalid", "$.decision", "Decision must be APPROVED or REJECTED");
    if (reason == null || !reason.matches("^[A-Z][A-Z0-9_]{2,127}$"))
      throw problem(422, "approval_reason_invalid", "$.reason_code", "Invalid reason code");
    if (comment != null && !comment.matches("^[A-Za-z0-9][A-Za-z0-9._:/-]{0,254}$"))
      throw problem(422, "approval_comment_ref_invalid", "$.comment_ref", "Invalid comment reference");
    return write.execute(status -> {
      var row = findForUpdate(key, null);
      if (row == null) throw problem(404, "approval_not_found", "$.approval_key", "Approval not found");
      var stored = decode(row);
      var now = clock.instant().truncatedTo(ChronoUnit.MICROS);
      if (!"PENDING".equals(stored.status())) {
        if (sameTerminalCommand(stored, actor, decision, reason, comment))
          return new ApprovalOutcome(stored.payload(), true);
        throw problem(409, "approval_terminal_conflict", "$.decision", "Approval already has a different terminal outcome");
      }
      if ("PENDING".equals(stored.status()) && !now.isBefore(stored.expiresAt()))
        throw problem(409, "approval_window_expired", "$.request.expires_at", "Approval window has expired");
      var terminal = terminal(stored.payload(), actor, decision, reason, comment, now);
      var candidate = validator.validate(terminal);
      var affected = jdbc.update(
          "UPDATE business_approvals SET revision=2,status=?,actor_id=?,decided_at=?,outcome_reason_code=?,comment_ref=?,canonical_sha256=?,payload=?,updated_at=? WHERE approval_id=? AND revision=1 AND status='PENDING'",
          decision, actor, now, reason, comment, candidate.sha256(), text(candidate), now, candidate.approvalId());
      if (affected != 1) throw new IllegalStateException("approval CAS did not update exactly one row");
      insertHistory(candidate, now);
      return new ApprovalOutcome(candidate.payload(), false);
    });
  }

  public ApprovalOutcome get(String key) {
    return read.execute(status -> {
      var rows = jdbc.queryForList("SELECT * FROM business_approvals WHERE approval_key=?", key);
      if (rows.isEmpty()) throw problem(404, "approval_not_found", "$.approval_key", "Approval not found");
      var approval = decode(rows.get(0));
      validateHistory(approval);
      return new ApprovalOutcome(approval.payload(), false);
    });
  }

  private boolean insertCurrent(ValidatedApproval value) {
    var now = clock.instant().truncatedTo(ChronoUnit.MICROS);
    jdbc.queryForObject("SELECT LAST_INSERT_ID(1)", Long.class);
    jdbc.update(
        "INSERT INTO business_approvals (approval_id,approval_key,decision_id,decision_key,fusion_id,fusion_key,run_id,incident_id,coordinator_execution_id,fusion_round,proposed_action,risk_level,requested_at,expires_at,revision,status,canonical_sha256,payload,created_at,updated_at) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,1,'PENDING',?,?,?,?) ON DUPLICATE KEY UPDATE revision=revision+(0*LAST_INSERT_ID(0))",
        value.approvalId(), value.approvalKey(), value.decisionId(), value.decisionKey(), value.fusionId(), value.fusionKey(), value.runId(), value.incidentId(), value.coordinatorExecutionId(), value.round(), value.proposedAction(), value.riskLevel(), value.requestedAt(), value.expiresAt(), value.sha256(), text(value), now, now);
    var marker = jdbc.queryForObject("SELECT LAST_INSERT_ID()", Long.class);
    return marker != null && marker == 1L;
  }

  private Map<String, Object> findForUpdate(String key, String id) {
    var rows = id == null
        ? jdbc.queryForList("SELECT * FROM business_approvals WHERE approval_key=? FOR UPDATE", key)
        : jdbc.queryForList("SELECT * FROM business_approvals WHERE approval_key=? OR approval_id=? FOR UPDATE", key, id);
    if (rows.size() > 1) throw new IllegalStateException("approval key/id split integrity failure");
    return rows.isEmpty() ? null : rows.get(0);
  }

  private void requireIdentity(Map<String, Object> row, ValidatedApproval value) {
    if (!value.approvalId().equals(row.get("approval_id")) || !value.approvalKey().equals(row.get("approval_key")))
      throw problem(409, "approval_identity_conflict", "$.identity", "Approval key/id split conflicts with an existing approval");
  }

  private ValidatedApproval decode(Map<String, Object> row) {
    try {
      var payload = mapper.readTree((String) row.get("payload"));
      var value = validator.validate(payload);
      if (!Arrays.equals((byte[]) row.get("canonical_sha256"), value.sha256())
          || !value.status().equals(row.get("status"))
          || value.revision() != ((Number) row.get("revision")).intValue()
          || !value.approvalId().equals(row.get("approval_id"))
          || !value.approvalKey().equals(row.get("approval_key"))
          || !value.decisionId().equals(row.get("decision_id"))
          || !value.decisionKey().equals(row.get("decision_key"))
          || !value.fusionId().equals(row.get("fusion_id"))
          || !value.fusionKey().equals(row.get("fusion_key"))
          || !value.runId().equals(row.get("run_id"))
          || !java.util.Objects.equals(value.incidentId(), row.get("incident_id"))
          || !value.coordinatorExecutionId().equals(row.get("coordinator_execution_id"))
          || value.round() != ((Number) row.get("fusion_round")).intValue()
          || !value.proposedAction().equals(row.get("proposed_action"))
          || !value.riskLevel().equals(row.get("risk_level"))
          || !value.requestedAt().equals(databaseInstant(row.get("requested_at")))
          || !value.expiresAt().equals(databaseInstant(row.get("expires_at")))
          || !java.util.Objects.equals(value.actorId(), row.get("actor_id"))
          || !java.util.Objects.equals(value.decidedAt(), databaseInstant(row.get("decided_at")))
          || !java.util.Objects.equals(value.reasonCode(), row.get("outcome_reason_code"))
          || !java.util.Objects.equals(value.commentRef(), row.get("comment_ref")))
        throw integrity("approval persisted representation is corrupt");
      return value;
    } catch (ApprovalProblem error) { throw error; }
    catch (Exception error) { throw integrity("approval payload cannot be decoded"); }
  }

  private void validateHistory(ValidatedApproval current) {
    var rows = jdbc.queryForList(
        "SELECT * FROM business_approval_history WHERE approval_id=? ORDER BY revision",
        current.approvalId());
    if (rows.size() != current.revision()) throw integrity("approval history is incomplete");
    ValidatedApproval previous = null;
    for (var row : rows) {
      try {
        var payload = mapper.readTree((String) row.get("payload"));
        var value = validator.validate(payload);
        if (!Arrays.equals((byte[]) row.get("canonical_sha256"), value.sha256())
            || !current.approvalId().equals(value.approvalId())
            || value.revision() != ((Number) row.get("revision")).intValue()
            || !value.status().equals(row.get("status"))
            || !java.util.Objects.equals(value.actorId(), row.get("actor_id")))
          throw integrity("approval history representation is corrupt");
        if (previous == null) {
          if (value.revision() != 1 || !"PENDING".equals(value.status()))
            throw integrity("approval history does not begin with PENDING revision 1");
        } else if (value.revision() != 2
            || !previous.payload().path("identity").equals(value.payload().path("identity"))
            || !previous.payload().path("request").equals(value.payload().path("request"))) {
          throw integrity("approval history revision changed immutable facts");
        }
        previous = value;
      } catch (ApprovalProblem error) { throw integrity("approval history contract is invalid"); }
      catch (Exception error) { throw integrity("approval history cannot be decoded"); }
    }
    if (previous == null || !Arrays.equals(previous.sha256(), current.sha256()))
      throw integrity("approval current is not the latest history revision");
  }

  private ObjectNode terminal(ObjectNode pending, String actor, String decision, String reason, String comment, Instant now) {
    var payload = pending.deepCopy();
    var state = (ObjectNode) payload.path("state");
    state.put("revision", 2).put("status", decision);
    var outcome = mapper.createObjectNode().put("actor_type", "HUMAN").put("actor_id", actor)
        .put("decided_at", UTC_MICROS.format(now)).put("reason_code", reason);
    if (comment != null) outcome.put("comment_ref", comment);
    state.set("outcome", outcome);
    return payload;
  }

  private boolean sameTerminalCommand(
      ValidatedApproval stored, String actor, String decision, String reason, String comment) {
    return decision.equals(stored.status())
        && actor.equals(stored.actorId())
        && reason.equals(stored.reasonCode())
        && java.util.Objects.equals(comment, stored.commentRef());
  }

  private void insertHistory(ValidatedApproval value, Instant at) {
    jdbc.update("INSERT INTO business_approval_history (approval_id,revision,status,actor_id,canonical_sha256,payload,recorded_at) VALUES (?,?,?,?,?,?,?)",
        value.approvalId(), value.revision(), value.status(), value.actorId(), value.sha256(), text(value), at.truncatedTo(ChronoUnit.MICROS));
  }

  private static String text(ValidatedApproval value) { return new String(value.canonical(), StandardCharsets.UTF_8); }
  private static Instant databaseInstant(Object value) {
    if (value == null) return null;
    if (value instanceof java.sql.Timestamp timestamp) return timestamp.toInstant();
    if (value instanceof java.time.LocalDateTime local) return local.toInstant(ZoneOffset.UTC);
    throw integrity("approval timestamp projection has an unexpected type");
  }
  private static ApprovalProblem problem(int status, String code, String path, String message) { return new ApprovalProblem(status, code, path, message); }
  private static ApprovalProblem integrity(String message) { return problem(500, "approval_integrity_error", "$", message); }
}
