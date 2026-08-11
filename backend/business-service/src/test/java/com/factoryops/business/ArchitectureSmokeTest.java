package com.factoryops.business;

import static org.assertj.core.api.Assertions.assertThatCode;

import org.junit.jupiter.api.Test;

class ArchitectureSmokeTest {

    @Test
    void exposes_a_spring_boot_application_entry_point() {
        assertThatCode(() -> Class.forName("com.factoryops.business.FactoryOpsBusinessApplication"))
                .doesNotThrowAnyException();
    }
}
