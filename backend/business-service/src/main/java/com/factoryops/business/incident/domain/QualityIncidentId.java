package com.factoryops.business.incident.domain;

import java.nio.charset.StandardCharsets;
import java.security.MessageDigest;
import java.security.NoSuchAlgorithmException;
import java.util.HexFormat;

public final class QualityIncidentId {
  private static final String NAMESPACE = "factoryops:quality-incident:v1:result:";

  private QualityIncidentId() {}

  public static String fromResultId(String resultId) {
    requireText(resultId, "result_id");
    try {
      var digest = MessageDigest.getInstance("SHA-256");
      var hash = digest.digest((NAMESPACE + resultId).getBytes(StandardCharsets.UTF_8));
      return "QI-" + HexFormat.of().withUpperCase().formatHex(hash);
    } catch (NoSuchAlgorithmException impossible) {
      throw new IllegalStateException(impossible);
    }
  }

  static void requireText(String value, String field) {
    if (value == null || value.isBlank()) {
      throw new IllegalArgumentException(field + " must not be blank");
    }
  }
}
