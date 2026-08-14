package com.factoryops.business.outbox.publisher;

import com.factoryops.business.outbox.domain.OutboxEvent;
import java.time.Instant;
import java.util.List;

@FunctionalInterface
public interface OutboxPublicationRepository {
  Instant markPublished(String eventId);

  default List<OutboxEvent> findPublishable(int limit) {
    throw new UnsupportedOperationException("publishable query is not implemented");
  }
}
