package com.factoryops.business.inspection.application;

import com.factoryops.business.inspection.domain.*;
import com.factoryops.business.inspection.infrastructure.InspectionJdbcRepository;
import com.factoryops.business.inspection.infrastructure.InspectionResultJdbcRepository;
import java.time.Clock;
import org.springframework.beans.factory.annotation.Qualifier;
import org.springframework.dao.DuplicateKeyException;
import org.springframework.stereotype.Service;
import org.springframework.transaction.support.TransactionTemplate;

@Service
public class InspectionApplicationService {
    private final InspectionJdbcRepository repository;
    private final InspectionResultJdbcRepository resultRepository;
    private final Clock clock;
    private final TransactionTemplate write;
    private final TransactionTemplate read;
    public InspectionApplicationService(InspectionJdbcRepository r, InspectionResultJdbcRepository rr, Clock c, @Qualifier("inspectionWriteTransaction") TransactionTemplate w, @Qualifier("inspectionReadTransaction") TransactionTemplate rd){
        repository=r;resultRepository=rr;clock=c;write=w;read=rd;
    }
    public Creation create(String id, InspectionInput input) {
        var found = read.execute(s -> repository.find(id).map(inspection -> compare(inspection, input)));
        if(found != null && found.isPresent()) return found.get();
        var candidate=Inspection.pending(id,input,clock.instant());
        try {
            write.executeWithoutResult(s->repository.insert(candidate));
            return new Creation(candidate,false,0);
        }
        catch(DuplicateKeyException e){
            return read.execute(s -> repository.find(id)
                    .map(inspection -> compare(inspection, input)))
                    .orElseThrow(() -> e);
        }
    }
    public InspectionDetails get(String id){
        return read.execute(s -> {
            var inspection = repository.find(id).orElseThrow(InspectionNotFoundException::new);
            return new InspectionDetails(inspection,resultRepository.countByInspectionId(id));
        });
    }
    private Creation compare(Inspection i,InspectionInput input){
        if(i.input().equals(input))return new Creation(i,true,resultRepository.countByInspectionId(i.id()));
        throw new InspectionIdentityConflictException();
    }
    public record Creation(Inspection inspection, boolean replayed, long resultCount){}
    public record InspectionDetails(Inspection inspection, long resultCount){}
}
