package com.factoryops.business.inspection.infrastructure;

import com.factoryops.business.inspection.application.VisionInspectionContractValidator;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;
import org.springframework.transaction.PlatformTransactionManager;
import org.springframework.transaction.TransactionDefinition;
import org.springframework.transaction.support.TransactionTemplate;
import tools.jackson.databind.json.JsonMapper;
import java.time.Clock;
import org.springframework.beans.factory.annotation.Value;

@Configuration
public class InspectionTransactionConfiguration {
    @Bean Clock factoryOpsClock(@Value("${factoryops.clock.fixed:}") String fixed) { return fixed.isBlank()?Clock.systemUTC():Clock.fixed(java.time.Instant.parse(fixed),java.time.ZoneOffset.UTC); }
    @Bean
    VisionInspectionContractValidator visionInspectionContractValidator(JsonMapper mapper) {
        return new VisionInspectionContractValidator(mapper);
    }

    @Bean("inspectionWriteTransaction")
    TransactionTemplate inspectionWriteTransaction(PlatformTransactionManager manager) {
        return readCommitted(manager, false);
    }

    @Bean("inspectionReadTransaction")
    TransactionTemplate inspectionReadTransaction(PlatformTransactionManager manager) {
        return readCommitted(manager, true);
    }

    private TransactionTemplate readCommitted(PlatformTransactionManager manager, boolean readOnly) {
        var template = new TransactionTemplate(manager);
        template.setIsolationLevel(TransactionDefinition.ISOLATION_READ_COMMITTED);
        template.setReadOnly(readOnly);
        return template;
    }
}
