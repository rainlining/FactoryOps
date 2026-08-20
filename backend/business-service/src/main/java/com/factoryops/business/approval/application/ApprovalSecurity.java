package com.factoryops.business.approval.application;

import java.nio.charset.StandardCharsets;
import java.security.MessageDigest;
import java.util.Arrays;
import java.util.Map;
import java.util.stream.Collectors;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.stereotype.Component;

@Component
public final class ApprovalSecurity {
  private final String serviceToken;
  private final Map<String, String> actors;

  public ApprovalSecurity(
      @Value("${factoryops.approval.service-token:}") String serviceToken,
      @Value("${factoryops.approval.authorized-actors:}") String actorList) {
    this.serviceToken = serviceToken;
    this.actors = Arrays.stream(actorList.split(","))
        .map(String::trim).filter(value -> !value.isEmpty())
        .map(value -> value.split(":", 2))
        .filter(parts -> parts.length == 2 && !parts[0].isBlank() && !parts[1].isBlank())
        .collect(Collectors.toUnmodifiableMap(parts -> parts[0], parts -> parts[1]));
  }

  public void requireService(String supplied) {
    if (serviceToken.isBlank() || supplied == null || !MessageDigest.isEqual(
        serviceToken.getBytes(StandardCharsets.UTF_8), supplied.getBytes(StandardCharsets.UTF_8)))
      throw new ApprovalProblem(403, "approval_service_forbidden", "$header.X-FactoryOps-Service-Token", "Trusted service token required");
  }

  public String requireActor(String actorId, String actorToken) {
    var expected = actorId == null ? null : actors.get(actorId);
    if (expected == null || actorToken == null || !MessageDigest.isEqual(
        expected.getBytes(StandardCharsets.UTF_8), actorToken.getBytes(StandardCharsets.UTF_8)))
      throw new ApprovalProblem(403, "approval_actor_forbidden", "$header.X-FactoryOps-Actor-Id", "Actor is not authorized");
    return actorId;
  }
}
