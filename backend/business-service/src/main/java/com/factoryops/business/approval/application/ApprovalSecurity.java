package com.factoryops.business.approval.application;

import java.nio.charset.StandardCharsets;
import java.security.MessageDigest;
import java.util.Arrays;
import java.util.Set;
import java.util.stream.Collectors;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.stereotype.Component;

@Component
public final class ApprovalSecurity {
  private final String serviceToken;
  private final Set<String> actors;

  public ApprovalSecurity(
      @Value("${factoryops.approval.service-token:}") String serviceToken,
      @Value("${factoryops.approval.authorized-actors:}") String actorList) {
    this.serviceToken = serviceToken;
    this.actors = Arrays.stream(actorList.split(","))
        .map(String::trim).filter(value -> !value.isEmpty()).collect(Collectors.toUnmodifiableSet());
  }

  public void requireService(String supplied) {
    if (serviceToken.isBlank() || supplied == null || !MessageDigest.isEqual(
        serviceToken.getBytes(StandardCharsets.UTF_8), supplied.getBytes(StandardCharsets.UTF_8)))
      throw new ApprovalProblem(403, "approval_service_forbidden", "$header.X-FactoryOps-Service-Token", "Trusted service token required");
  }

  public String requireActor(String actorId) {
    if (actorId == null || !actors.contains(actorId))
      throw new ApprovalProblem(403, "approval_actor_forbidden", "$header.X-FactoryOps-Actor-Id", "Actor is not authorized");
    return actorId;
  }
}
