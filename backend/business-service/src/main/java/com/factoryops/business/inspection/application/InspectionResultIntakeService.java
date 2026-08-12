package com.factoryops.business.inspection.application;

import com.factoryops.business.inspection.infrastructure.InspectionResultJdbcRepository;
import com.factoryops.business.inspection.infrastructure.InspectionJdbcRepository;
import com.factoryops.business.inspection.domain.InspectionInput;
import java.time.Clock;
import java.util.Arrays;
import org.springframework.beans.factory.annotation.Qualifier;
import org.springframework.dao.DuplicateKeyException;
import org.springframework.stereotype.Service;
import org.springframework.transaction.support.TransactionTemplate;
import tools.jackson.databind.JsonNode;

@Service
public class InspectionResultIntakeService implements InspectionResultIntake {
    private final VisionInspectionContractValidator validator;
    private final InspectionResultJdbcRepository repository;
    private final InspectionJdbcRepository inspections;
    private final Clock clock;
    private final TransactionTemplate writeTransaction;
    private final TransactionTemplate readTransaction;

    public InspectionResultIntakeService(VisionInspectionContractValidator validator,
            InspectionResultJdbcRepository repository,
            InspectionJdbcRepository inspections, Clock clock,
            @Qualifier("inspectionWriteTransaction") TransactionTemplate writeTransaction,
            @Qualifier("inspectionReadTransaction") TransactionTemplate readTransaction) {
        this.validator = validator;
        this.repository = repository;
        this.inspections = inspections; this.clock = clock;
        this.writeTransaction = writeTransaction;
        this.readTransaction = readTransaction;
    }

    @Override
    public IntakeDisposition accept(JsonNode payload) {
        var result = validator.validate(payload);
        try { return writeTransaction.execute(status -> {
            var inspection=inspections.find(result.inspectionId()).orElseThrow(ResultInspectionNotFoundException::new);
            var mismatch=inspection.input().firstMismatch(new InspectionInput(result.imageUri(),result.imageSha256()));
            if(mismatch.isPresent()) throw new InspectionInputMismatchException(mismatch.get());
            var existing=repository.findByResultId(result.resultId()); if(existing.isPresent()) return compare(result,existing.get());
            repository.insert(result); inspections.completePending(result.inspectionId(),clock.instant()); return IntakeDisposition.CREATED;
        }); } catch (DuplicateKeyException duplicate) {
            var winner = readTransaction.execute(status -> repository.findByResultId(result.resultId()))
                    .orElseThrow(() -> duplicate);
            return compare(result, winner);
        }
    }

    private IntakeDisposition compare(ValidatedVisionResult candidate,
            com.factoryops.business.inspection.infrastructure.StoredInspectionResult existing) {
        if (Arrays.equals(candidate.payloadHash(), existing.payloadHash())) return IntakeDisposition.REPLAYED;
        throw new ResultIdentityConflictException(candidate.resultId());
    }
}
