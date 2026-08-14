package com.factoryops.business.outbox.publisher;

import java.time.Duration;

public record KafkaPublication(int partition, long offset, Duration acknowledgementLatency) {}
