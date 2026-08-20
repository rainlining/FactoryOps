package com.factoryops.business.approval.application;

import com.factoryops.business.inspection.application.CanonicalJson;
import com.networknt.schema.Schema;
import com.networknt.schema.SchemaRegistry;
import com.networknt.schema.SpecificationVersion;
import java.io.IOException;
import java.nio.charset.StandardCharsets;
import java.security.MessageDigest;
import java.time.Instant;
import java.util.Comparator;
import java.util.HexFormat;
import java.util.Map;
import org.springframework.stereotype.Component;
import tools.jackson.databind.JsonNode;
import tools.jackson.databind.json.JsonMapper;
import tools.jackson.databind.node.ArrayNode;
import tools.jackson.databind.node.ObjectNode;

@Component
public final class HumanApprovalContractValidator {
  private final Map<String, Schema> schemas;

  public HumanApprovalContractValidator(JsonMapper mapper) {
    schemas = Map.of("1.0.0", load(mapper, "1.0.0"), "1.1.0", load(mapper, "1.1.0"));
  }

  public ValidatedApproval validate(JsonNode input) {
    var version = input.path("contract_version").asText();
    var schema = schemas.get(version);
    if (schema == null)
      throw problem("approval_contract_invalid", "$.contract_version", "Unsupported Human Approval contract version");
    var errors = schema.validate(input);
    if (!errors.isEmpty()) {
      var first = errors.stream().min(Comparator.comparing(e -> e.getInstanceLocation().toString())).orElseThrow();
      throw problem("approval_contract_invalid", jsonPath(first.getInstanceLocation().toString()), first.getMessage());
    }
    var payload = (ObjectNode) input.deepCopy();
    sort((ArrayNode) payload.path("request").path("policy_refs"));
    sort((ArrayNode) payload.path("request").path("reason_codes"));
    var identity = payload.path("identity");
    var request = payload.path("request");
    var state = payload.path("state");
    var decisionKey = identity.path("decision_key").asText();
    var expectedKey = approvalKey(decisionKey);
    if (!expectedKey.equals(identity.path("approval_key").asText()))
      throw problem("approval_key_mismatch", "$.identity.approval_key", "Approval key does not match decision key");
    if (!("APR-" + expectedKey.substring(4, 36)).equals(identity.path("approval_id").asText()))
      throw problem("approval_id_mismatch", "$.identity.approval_id", "Approval id does not match decision key");
    if (hasDuplicates((ArrayNode) request.path("policy_refs")) || hasDuplicates((ArrayNode) request.path("reason_codes")))
      throw problem("duplicate_value", "$.request", "Set-like request arrays must contain unique values");
    var requestedAt = instant(request.path("requested_at").asText(), "$.request.requested_at");
    var expiresAt = instant(request.path("expires_at").asText(), "$.request.expires_at");
    if (!requestedAt.isBefore(expiresAt))
      throw problem("invalid_time_order", "$.request.expires_at", "expires_at must be after requested_at");
    String actor = null, reason = null, comment = null;
    Instant decidedAt = null;
    if (state.has("outcome")) {
      var outcome = state.path("outcome");
      actor = outcome.path("actor_id").asText();
      reason = outcome.path("reason_code").asText();
      comment = outcome.has("comment_ref") ? outcome.path("comment_ref").asText() : null;
      decidedAt = instant(outcome.path("decided_at").asText(), "$.state.outcome.decided_at");
      var status = state.path("status").asText();
      if (!"HUMAN".equals(outcome.path("actor_type").asText()) || !("APPROVED".equals(status) || "REJECTED".equals(status)))
        throw problem("actor_type_mismatch", "$.state.outcome.actor_type", "Human API only accepts human terminal outcomes");
      if (decidedAt.isBefore(requestedAt) || !decidedAt.isBefore(expiresAt))
        throw problem("approval_window_expired", "$.request.expires_at", "Human decision must be before expires_at");
    }
    var canonical = CanonicalJson.canonicalize(payload);
    return new ValidatedApproval(
        version, identity.path("approval_id").asText(), expectedKey,
        identity.path("decision_id").asText(), decisionKey,
        identity.path("fusion_id").asText(), identity.path("fusion_key").asText(),
        identity.path("run_id").asText(), identity.has("incident_id") ? identity.path("incident_id").asText() : null,
        identity.path("coordinator_execution_id").asText(),
        identity.path("round").asInt(), request.path("proposed_action").asText(),
        request.path("risk_level").asText(), requestedAt, expiresAt,
        state.path("revision").asInt(), state.path("status").asText(), actor, decidedAt,
        reason, comment, payload, canonical, CanonicalJson.sha256(payload));
  }

  private Schema load(JsonMapper mapper, String version) {
    try (var input = getClass().getResourceAsStream("/contracts/human_approval/v" + version + "/schema.json")) {
      if (input == null) throw new IllegalStateException("Human Approval schema is missing: " + version);
      return SchemaRegistry.withDefaultDialect(SpecificationVersion.DRAFT_2020_12)
          .getSchema(mapper.readTree(input));
    } catch (IOException error) {
      throw new IllegalStateException("Cannot load Human Approval schema: " + version, error);
    }
  }

  private static String approvalKey(String decisionKey) {
    try {
      var bytes = MessageDigest.getInstance("SHA-256").digest(("v1\n" + decisionKey).getBytes(StandardCharsets.UTF_8));
      return "APK-" + HexFormat.of().withUpperCase().formatHex(bytes);
    } catch (Exception impossible) { throw new IllegalStateException(impossible); }
  }

  private static Instant instant(String value, String path) {
    try { return Instant.parse(value); }
    catch (RuntimeException error) { throw problem("invalid_timestamp", path, "Timestamp must be UTC ISO-8601"); }
  }

  private static void sort(ArrayNode values) {
    var sorted = new java.util.ArrayList<String>();
    values.forEach(v -> sorted.add(v.asText()));
    sorted.sort(String::compareTo);
    values.removeAll();
    sorted.forEach(values::add);
  }

  private static boolean hasDuplicates(ArrayNode values) {
    var seen = new java.util.HashSet<String>();
    for (var value : values) if (!seen.add(value.asText())) return true;
    return false;
  }

  private static ApprovalProblem problem(String code, String path, String message) {
    return new ApprovalProblem(422, code, path, message);
  }

  private static String jsonPath(String pointer) {
    if (pointer.isEmpty()) return "$";
    return "$" + pointer.replace("/", ".").replace("~1", "/").replace("~0", "~");
  }
}
