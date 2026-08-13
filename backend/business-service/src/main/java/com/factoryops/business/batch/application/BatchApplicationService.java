package com.factoryops.business.batch.application;

import com.factoryops.business.batch.domain.*;
import com.factoryops.business.batch.infrastructure.BatchJdbcRepository;
import com.factoryops.business.inspection.infrastructure.*;
import java.time.Clock;
import org.springframework.beans.factory.annotation.Qualifier;
import org.springframework.dao.DuplicateKeyException;
import org.springframework.stereotype.Service;
import org.springframework.transaction.support.TransactionTemplate;

@Service
public class BatchApplicationService {
  private final BatchJdbcRepository batches;
  private final InspectionJdbcRepository inspections;
  private final InspectionResultJdbcRepository results;
  private final Clock clock;
  private final TransactionTemplate write, read;

  public BatchApplicationService(
      BatchJdbcRepository b,
      InspectionJdbcRepository i,
      InspectionResultJdbcRepository r,
      Clock c,
      @Qualifier("inspectionWriteTransaction") TransactionTemplate w,
      @Qualifier("inspectionReadTransaction") TransactionTemplate rd) {
    batches = b;
    inspections = i;
    results = r;
    clock = c;
    write = w;
    read = rd;
  }

  public Outcome create(String id, String product, String line) {
    var existing = read.execute(s -> batches.find(id));
    if (existing != null && existing.isPresent()) return compare(existing.get(), product, line);
    var candidate = Batch.production(id, product, line, clock.instant());
    try {
      write.executeWithoutResult(s -> batches.insert(candidate));
      return new Outcome(candidate, false);
    } catch (DuplicateKeyException e) {
      return compare(read.execute(s -> batches.find(id)).orElseThrow(() -> e), product, line);
    }
  }

  public Batch get(String id) {
    return read.execute(s -> batches.find(id)).orElseThrow(BatchNotFoundException::new);
  }

  public Outcome hold(String id, HoldCommand command) {
    return write.execute(
        s -> {
          var b = batches.findForUpdate(id).orElseThrow(BatchNotFoundException::new);
          if (b.kind() != BatchKind.PRODUCTION) throw new BatchNotActionableException();
          if (b.status() != BatchStatus.OPEN) {
            var d = b.hold(command, clock.instant());
            return new Outcome(b, d == CommandDisposition.REPLAYED);
          }
          if (command.reasonCode() == HoldReasonCode.QUALITY_ANOMALY) validateEvidence(id, command);
          batches.holdOpen(id, command, clock.instant());
          return new Outcome(batches.find(id).orElseThrow(), false);
        });
  }

  public Outcome release(String id, ReleaseCommand command) {
    return write.execute(
        s -> {
          var b = batches.findForUpdate(id).orElseThrow(BatchNotFoundException::new);
          var now = clock.instant();
          var d = b.release(command, now);
          if (d == CommandDisposition.APPLIED) batches.releaseHeld(id, command, now);
          return new Outcome(batches.find(id).orElseThrow(), d == CommandDisposition.REPLAYED);
        });
  }

  private void validateEvidence(String batchId, HoldCommand c) {
    var i =
        inspections
            .find(c.inspectionId())
            .orElseThrow(() -> new HoldEvidenceException("hold_evidence_not_found"));
    if (!i.batchId().equals(batchId)) throw new HoldEvidenceException("hold_evidence_mismatch");
    var r =
        results
            .findEvidence(c.resultId())
            .orElseThrow(() -> new HoldEvidenceException("hold_evidence_not_found"));
    if (!r.inspectionId().equals(i.id())) throw new HoldEvidenceException("hold_evidence_mismatch");
    if (!r.anomaly()) throw new HoldEvidenceException("hold_evidence_not_anomalous");
  }

  private Outcome compare(Batch b, String p, String l) {
    if (b.productCode().equals(p) && b.productionLine().equals(l)) return new Outcome(b, true);
    throw new BatchIdentityConflictException();
  }

  public record Outcome(Batch batch, boolean replayed) {}
}
