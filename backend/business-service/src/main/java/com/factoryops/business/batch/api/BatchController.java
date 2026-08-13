package com.factoryops.business.batch.api;

import com.factoryops.business.batch.application.*;
import com.factoryops.business.batch.domain.*;
import org.springframework.http.*;
import org.springframework.web.bind.annotation.*;

@RestController
@RequestMapping("/api/v1/batches")
public class BatchController {
  private final BatchApplicationService service;

  public BatchController(BatchApplicationService s) {
    service = s;
  }

  @PostMapping
  ResponseEntity<BatchResponse> create(@RequestBody BatchCreateRequest r) {
    try {
      var o = service.create(r.batchId(), r.productCode(), r.productionLine());
      return ResponseEntity.status(o.replayed() ? 200 : 201).body(response(o));
    } catch (IllegalArgumentException e) {
      throw requestError(e);
    }
  }

  @GetMapping("/{id}")
  BatchResponse get(@PathVariable String id) {
    return response(service.get(id));
  }

  @PostMapping("/{id}/hold")
  BatchResponse hold(@PathVariable String id, @RequestBody BatchHoldRequest r) {
    try {
      return response(
          service.hold(
              id,
              new HoldCommand(
                  HoldReasonCode.valueOf(r.reasonCode()),
                  r.reasonDetail(),
                  r.inspectionId(),
                  r.resultId())));
    } catch (IllegalArgumentException | NullPointerException e) {
      throw new BatchRequestException(
          "invalid_hold_command", "$.reason_code", "Invalid hold command");
    }
  }

  private BatchRequestException requestError(IllegalArgumentException e) {
    var message = e.getMessage();
    if ("reserved batch_id".equals(message))
      return new BatchRequestException("reserved_batch_id", "$.batch_id", message);
    if ("invalid product_code".equals(message))
      return new BatchRequestException("invalid_product_code", "$.product_code", message);
    if ("invalid production_line".equals(message))
      return new BatchRequestException("invalid_production_line", "$.production_line", message);
    return new BatchRequestException("invalid_batch_id", "$.batch_id", "Invalid batch id");
  }

  private BatchResponse response(BatchApplicationService.Outcome o) {
    var b = o.batch();
    var h = b.holdCommand();
    var rel = b.releaseCommand();
    return new BatchResponse(
        b.id(),
        b.kind().name(),
        b.productCode(),
        b.productionLine(),
        b.status().name(),
        b.createdAt(),
        b.heldAt(),
        h == null ? null : h.reasonCode().name(),
        h == null ? null : h.reasonDetail(),
        h == null ? null : h.inspectionId(),
        h == null ? null : h.resultId(),
        b.releasedAt(),
        rel == null ? null : rel.reasonCode().name(),
        rel == null ? null : rel.reasonDetail(),
        o.inspectionCount(), o.replayed());
  }
}
