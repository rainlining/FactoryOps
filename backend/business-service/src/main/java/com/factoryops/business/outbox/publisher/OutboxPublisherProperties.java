package com.factoryops.business.outbox.publisher;

import java.time.Duration;
import org.springframework.boot.context.properties.ConfigurationProperties;

@ConfigurationProperties("factoryops.outbox.publisher")
public class OutboxPublisherProperties {
  private boolean enabled;
  private Duration pollDelay = Duration.ofSeconds(1);
  private int batchSize = 50;
  private Duration deliveryTimeout = Duration.ofSeconds(10);

  public boolean isEnabled() {
    return enabled;
  }

  public void setEnabled(boolean enabled) {
    this.enabled = enabled;
  }

  public Duration getPollDelay() {
    return pollDelay;
  }

  public void setPollDelay(Duration pollDelay) {
    this.pollDelay = pollDelay;
  }

  public int getBatchSize() {
    return batchSize;
  }

  public void setBatchSize(int batchSize) {
    this.batchSize = batchSize;
  }

  public Duration getDeliveryTimeout() {
    return deliveryTimeout;
  }

  public void setDeliveryTimeout(Duration deliveryTimeout) {
    this.deliveryTimeout = deliveryTimeout;
  }
}
