package com.factoryops.business.approval.application;

import com.factoryops.business.batch.application.BatchApplicationService;
import com.factoryops.business.batch.domain.HoldCommand;
import com.factoryops.business.batch.domain.HoldReasonCode;
import java.time.Clock;
import java.time.Instant;
import java.time.temporal.ChronoUnit;
import java.util.Map;
import org.springframework.beans.factory.annotation.Qualifier;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.stereotype.Service;
import org.springframework.transaction.support.TransactionTemplate;

@Service
public final class ApprovedBatchHoldExecutionService {
  private final JdbcTemplate jdbc;
  private final TransactionTemplate write;
  private final HumanApprovalApplicationService approvals;
  private final BatchApplicationService batches;
  private final Clock clock;

  public ApprovedBatchHoldExecutionService(
      JdbcTemplate jdbc,
      @Qualifier("inspectionWriteTransaction") TransactionTemplate write,
      HumanApprovalApplicationService approvals,
      BatchApplicationService batches,
      Clock clock) {
    this.jdbc = jdbc;
    this.write = write;
    this.approvals = approvals;
    this.batches = batches;
    this.clock = clock;
  }

  public ActionExecutionOutcome execute(String approvalKey) {
    var candidates = jdbc.queryForList(
        "SELECT incident_id FROM business_approvals WHERE approval_key=?", approvalKey);
    if (candidates.isEmpty()) throw problem(404, "approval_not_found", "$.approval_key", "Approval not found");
    var candidateIncident = (String) candidates.get(0).get("incident_id");
    return write.execute(status -> executeLocked(approvalKey, candidateIncident));
  }

  private ActionExecutionOutcome executeLocked(String approvalKey, String candidateIncident) {
    var incidents = jdbc.queryForList(
        "SELECT incident_id,batch_id FROM quality_incidents WHERE incident_id_hash=UNHEX(SHA2(?,256)) AND incident_id=? FOR SHARE",
        candidateIncident, candidateIncident);
    if (incidents.size() != 1)
      throw problem(409, "approval_target_invalid", "$.identity.incident_id", "Approval target does not exist");
    var approvalRow = approvals.findForUpdate(approvalKey, null);
    if (approvalRow == null) throw problem(404, "approval_not_found", "$.approval_key", "Approval not found");
    var approval = approvals.decode(approvalRow);
    approvals.validateHistory(approval);
    if (!candidateIncident.equals(approval.incidentId()))
      throw problem(409, "approval_target_changed", "$.identity.incident_id", "Approval target changed during execution");
    if (!"APPROVED".equals(approval.status()) || approval.revision() != 2)
      throw problem(409, "approval_not_approved", "$.state.status", "Approval is not APPROVED");
    if (!"HOLD_BATCH".equals(approval.proposedAction()))
      throw problem(422, "approved_action_unsupported", "$.request.proposed_action", "Only HOLD_BATCH execution is supported");
    var batchId = (String) incidents.get(0).get("batch_id");
    var receipts = jdbc.queryForList(
        "SELECT * FROM approved_action_executions WHERE approval_id=? OR approval_key=? FOR UPDATE",
        approval.approvalId(), approval.approvalKey());
    if (receipts.size() > 1)
      throw problem(500, "action_execution_integrity_error", "$", "Action receipt identity is split");
    if (!receipts.isEmpty()) {
      validateExecutedBatch(batchId, approvalKey);
      return replay(receipts.get(0), approval, batchId);
    }
    batches.hold(batchId, HoldCommand.manual(HoldReasonCode.MANUAL_QUALITY_HOLD, "approval:" + approvalKey));
    var executedAt = clock.instant().truncatedTo(ChronoUnit.MICROS);
    jdbc.update(
        "INSERT INTO approved_action_executions (approval_id,approval_key,action,incident_id,batch_id,status,executed_at) VALUES (?,?,?,?,?,'EXECUTED',?)",
        approval.approvalId(), approvalKey, approval.proposedAction(), approval.incidentId(), batchId, executedAt);
    return new ActionExecutionOutcome(approvalKey, "HOLD_BATCH", approval.incidentId(), batchId, "EXECUTED", executedAt, false);
  }

  private void validateExecutedBatch(String batchId, String approvalKey) {
    var rows = jdbc.queryForList(
        "SELECT status,hold_reason_code,hold_reason_detail FROM batches WHERE batch_id_hash=UNHEX(SHA2(?,256)) AND batch_id=?",
        batchId, batchId);
    if (rows.size() != 1
        || !"HELD".equals(rows.get(0).get("status"))
        || !"MANUAL_QUALITY_HOLD".equals(rows.get(0).get("hold_reason_code"))
        || !("approval:" + approvalKey).equals(rows.get(0).get("hold_reason_detail")))
      throw problem(500, "action_execution_integrity_error", "$", "Executed Batch state is corrupt");
  }

  private static ActionExecutionOutcome replay(
      Map<String, Object> row, ValidatedApproval approval, String batchId) {
    if (!approval.approvalId().equals(row.get("approval_id"))
        || !approval.approvalKey().equals(row.get("approval_key"))
        || !approval.proposedAction().equals(row.get("action"))
        || !approval.incidentId().equals(row.get("incident_id"))
        || !batchId.equals(row.get("batch_id"))
        || !"EXECUTED".equals(row.get("status")))
      throw problem(500, "action_execution_integrity_error", "$", "Action receipt is corrupt");
    return new ActionExecutionOutcome(
        approval.approvalKey(), "HOLD_BATCH", approval.incidentId(), batchId, "EXECUTED",
        HumanApprovalApplicationService.databaseInstant(row.get("executed_at")), true);
  }

  private static ApprovalProblem problem(int status, String code, String path, String message) {
    return new ApprovalProblem(status, code, path, message);
  }
}
