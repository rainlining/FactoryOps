package com.factoryops.business.inspection.application;

import static org.assertj.core.api.Assertions.assertThat;

import java.nio.charset.StandardCharsets;
import org.junit.jupiter.api.Test;
import tools.jackson.databind.json.JsonMapper;

class CanonicalJsonTest {

    private final JsonMapper mapper = JsonMapper.builder().build();

    @Test
    void sorts_keys_normalizes_numbers_and_preserves_array_order() throws Exception {
        var input = mapper.readTree("""
                {"z":[2,1],"negativeZero":-0.0,"exponent":1E-3,"decimal":0.600,"a":true}
                """);

        var canonical = new String(CanonicalJson.canonicalize(input), StandardCharsets.UTF_8);

        assertThat(canonical)
                .isEqualTo("{\"a\":true,\"decimal\":0.6,\"exponent\":0.001,\"negativeZero\":0,\"z\":[2,1]}");
    }

    @Test
    void produces_stable_sha256() throws Exception {
        var left = mapper.readTree("{\"b\":1.0,\"a\":2}");
        var right = mapper.readTree("{\"a\":2.00,\"b\":1}");

        assertThat(CanonicalJson.sha256(left)).isEqualTo(CanonicalJson.sha256(right));
    }
}
