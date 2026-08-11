package com.factoryops.business.inspection.application;

import java.io.ByteArrayOutputStream;
import java.nio.charset.StandardCharsets;
import java.security.MessageDigest;
import java.security.NoSuchAlgorithmException;
import java.util.Comparator;
import tools.jackson.databind.JsonNode;
import tools.jackson.databind.json.JsonMapper;

public final class CanonicalJson {
    private static final JsonMapper MAPPER = JsonMapper.builder().build();

    private CanonicalJson() {
    }

    public static byte[] canonicalize(JsonNode node) {
        var output = new ByteArrayOutputStream();
        write(node, output);
        return output.toByteArray();
    }

    public static byte[] sha256(JsonNode node) {
        try {
            return MessageDigest.getInstance("SHA-256").digest(canonicalize(node));
        } catch (NoSuchAlgorithmException impossible) {
            throw new IllegalStateException("JVM does not provide SHA-256", impossible);
        }
    }

    private static void write(JsonNode node, ByteArrayOutputStream output) {
        if (node.isObject()) {
            output.write('{');
            var fields = node.properties().stream().sorted(Comparator.comparing(java.util.Map.Entry::getKey)).toList();
            for (int index = 0; index < fields.size(); index++) {
                if (index > 0) output.write(',');
                writeText(MAPPER.writeValueAsString(fields.get(index).getKey()), output);
                output.write(':');
                write(fields.get(index).getValue(), output);
            }
            output.write('}');
        } else if (node.isArray()) {
            output.write('[');
            for (int index = 0; index < node.size(); index++) {
                if (index > 0) output.write(',');
                write(node.get(index), output);
            }
            output.write(']');
        } else if (node.isNumber()) {
            var normalized = node.decimalValue().stripTrailingZeros();
            writeText(normalized.signum() == 0 ? "0" : normalized.toPlainString(), output);
        } else {
            writeText(node.toString(), output);
        }
    }

    private static void writeText(String value, ByteArrayOutputStream output) {
        output.writeBytes(value.getBytes(StandardCharsets.UTF_8));
    }
}
