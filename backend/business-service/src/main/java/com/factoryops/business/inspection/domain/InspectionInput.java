package com.factoryops.business.inspection.domain;

import java.net.URI;
import java.util.Optional;
import java.util.regex.Pattern;

public record InspectionInput(String imageUri, String sha256) {
    private static final Pattern SHA256 = Pattern.compile("[0-9a-f]{64}");

    public InspectionInput {
        try {
            if (imageUri == null || !URI.create(imageUri).isAbsolute()) throw new IllegalArgumentException("image_uri must be an absolute URI");
        } catch (RuntimeException error) {
            throw new IllegalArgumentException("image_uri must be an absolute URI", error);
        }
        if (sha256 == null || !SHA256.matcher(sha256).matches()) throw new IllegalArgumentException("sha256 must be 64 lowercase hexadecimal characters");
    }

    public Optional<String> firstMismatch(InspectionInput other) {
        if (!imageUri.equals(other.imageUri)) return Optional.of("$.input.image_uri");
        if (!sha256.equals(other.sha256)) return Optional.of("$.input.sha256");
        return Optional.empty();
    }
}
