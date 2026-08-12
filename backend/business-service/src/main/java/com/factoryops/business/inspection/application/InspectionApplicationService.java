package com.factoryops.business.inspection.application;

import com.factoryops.business.inspection.domain.*;
import com.factoryops.business.inspection.infrastructure.InspectionJdbcRepository;
import java.time.Clock;
import org.springframework.beans.factory.annotation.Qualifier;
import org.springframework.dao.DuplicateKeyException;
import org.springframework.stereotype.Service;
import org.springframework.transaction.support.TransactionTemplate;

@Service
public class InspectionApplicationService {
    private final InspectionJdbcRepository repository; private final Clock clock; private final TransactionTemplate write; private final TransactionTemplate read;
    public InspectionApplicationService(InspectionJdbcRepository r, Clock c, @Qualifier("inspectionWriteTransaction") TransactionTemplate w, @Qualifier("inspectionReadTransaction") TransactionTemplate rd){repository=r;clock=c;write=w;read=rd;}
    public Creation create(String id, InspectionInput input) {
        var found=read.execute(s->repository.find(id)); if(found!=null&&found.isPresent()) return compare(found.get(),input);
        var candidate=Inspection.pending(id,input,clock.instant());
        try { write.executeWithoutResult(s->repository.insert(candidate)); return new Creation(candidate,false); }
        catch(DuplicateKeyException e){var winner=read.execute(s->repository.find(id)).orElseThrow(()->e);return compare(winner,input);}
    }
    public Inspection get(String id){return read.execute(s->repository.find(id)).orElseThrow(InspectionNotFoundException::new);}
    private Creation compare(Inspection i,InspectionInput input){if(i.input().equals(input))return new Creation(i,true);throw new InspectionIdentityConflictException();}
    public record Creation(Inspection inspection, boolean replayed){}
}
