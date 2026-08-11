package com.factoryops.business.inspection.application;

import com.factoryops.business.inspection.infrastructure.InspectionResultJdbcRepository;
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
    private final TransactionTemplate writeTransaction;
    private final TransactionTemplate readTransaction;

    public InspectionResultIntakeService(VisionInspectionContractValidator validator,
            InspectionResultJdbcRepository repository,
            @Qualifier("inspectionWriteTransaction") TransactionTemplate writeTransaction,
            @Qualifier("inspectionReadTransaction") TransactionTemplate readTransaction) {
        this.validator = validator;
        this.repository = repository;
        this.writeTransaction = writeTransaction;
        this.readTransaction = readTransaction;
    }

    @Override
    public IntakeDisposition accept(JsonNode payload) {
        var result = validator.validate(payload);
        var existing = readTransaction.execute(status -> repository.findByResultId(result.resultId()));
        if (existing != null && existing.isPresent()) return compare(result, existing.get());
        try {
            writeTransaction.executeWithoutResult(status -> repository.insert(result));
            return IntakeDisposition.CREATED;
        } catch (DuplicateKeyException duplicate) {
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
