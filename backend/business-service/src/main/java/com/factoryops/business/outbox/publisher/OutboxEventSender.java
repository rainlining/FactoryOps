package com.factoryops.business.outbox.publisher;

import com.factoryops.business.outbox.domain.OutboxEvent;

@FunctionalInterface
public interface OutboxEventSender {
  KafkaPublication send(OutboxEvent event) throws Exception;
}
