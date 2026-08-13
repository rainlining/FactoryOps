package com.factoryops.business.batch.api;import com.factoryops.business.batch.application.*;import com.factoryops.business.batch.domain.*;import com.factoryops.business.inspection.api.ApiErrorResponse;import org.springframework.http.*;import org.springframework.web.bind.annotation.*;
@RestControllerAdvice public class BatchExceptionHandler {
 @ExceptionHandler(BatchNotFoundException.class)ResponseEntity<ApiErrorResponse>missing(){return ResponseEntity.status(404).body(new ApiErrorResponse("batch_not_found","$.batch_id","Batch not found"));}
 @ExceptionHandler(BatchIdentityConflictException.class)ResponseEntity<ApiErrorResponse>identity(){return ResponseEntity.status(409).body(new ApiErrorResponse("batch_identity_conflict","$.batch_id","Batch identity conflict"));}
 @ExceptionHandler(BatchCommandConflictException.class)ResponseEntity<ApiErrorResponse>command(){return ResponseEntity.status(409).body(new ApiErrorResponse("batch_command_conflict","$.reason_code","Batch command conflict"));}
 @ExceptionHandler(InvalidBatchTransitionException.class)ResponseEntity<ApiErrorResponse>transition(){return ResponseEntity.status(409).body(new ApiErrorResponse("invalid_batch_transition","$.status","Invalid batch transition"));}
 @ExceptionHandler(BatchNotActionableException.class)ResponseEntity<ApiErrorResponse>actionable(){return ResponseEntity.status(409).body(new ApiErrorResponse("batch_not_actionable","$.batch_id","Batch is not actionable"));}
 @ExceptionHandler(HoldEvidenceException.class)ResponseEntity<ApiErrorResponse>evidence(HoldEvidenceException e){return ResponseEntity.unprocessableEntity().body(new ApiErrorResponse(e.code(),"$.result_id","Invalid hold evidence"));}
}
