package com.factoryops.business.inspection.api;

import com.factoryops.business.inspection.application.InspectionResultIntake;
import com.factoryops.business.inspection.application.IntakeDisposition;
import org.springframework.http.HttpStatus;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;
import tools.jackson.databind.JsonNode;

@RestController
@RequestMapping("/api/v1/inspection-results")
public class InspectionResultController {
    private final InspectionResultIntake intake;

    public InspectionResultController(InspectionResultIntake intake) {
        this.intake = intake;
    }

    @PostMapping
    ResponseEntity<InspectionResultResponse> accept(@RequestBody JsonNode payload) {
        var disposition = intake.accept(payload);
        var status = disposition == IntakeDisposition.CREATED ? HttpStatus.CREATED : HttpStatus.OK;
        return ResponseEntity.status(status)
                .body(new InspectionResultResponse(disposition == IntakeDisposition.REPLAYED));
    }
}
