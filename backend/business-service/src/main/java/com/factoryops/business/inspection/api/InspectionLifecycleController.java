package com.factoryops.business.inspection.api;
import com.factoryops.business.inspection.application.InspectionApplicationService;
import com.factoryops.business.inspection.domain.*;
import org.springframework.http.*;
import org.springframework.web.bind.annotation.*;
@RestController
@RequestMapping("/api/v1/inspections")
public class InspectionLifecycleController {
    private final InspectionApplicationService service;
    public InspectionLifecycleController(InspectionApplicationService s){
        service=s;
    }
    @PostMapping
    ResponseEntity<InspectionLifecycleResponse> create(@RequestBody InspectionCreateRequest r){
        if(r.input()==null)throw new IllegalArgumentException("input is required");
        var c=service.create(r.inspectionId(),new InspectionInput(r.input().imageUri(),r.input().sha256()));
        return ResponseEntity.status(c.replayed()?HttpStatus.OK:HttpStatus.CREATED)
                .body(response(c.inspection(),c.resultCount(),c.replayed()));
    }
    @GetMapping("/{id}")
    InspectionLifecycleResponse get(@PathVariable String id){
        var details = service.get(id);
        return response(details.inspection(),details.resultCount(),false);
    }
    private InspectionLifecycleResponse response(Inspection i,long resultCount,boolean replayed){
        return new InspectionLifecycleResponse(i.id(),i.status().name(),new InspectionLifecycleResponse.Input(i.input().imageUri(),i.input().sha256()),i.createdAt(),i.completedAt(),resultCount,replayed);
    }
}
