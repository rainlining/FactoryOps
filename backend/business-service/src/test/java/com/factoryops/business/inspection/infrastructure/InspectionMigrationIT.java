package com.factoryops.business.inspection.infrastructure;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;

import java.sql.DriverManager;
import org.flywaydb.core.Flyway;
import org.junit.jupiter.api.Test;
import org.testcontainers.junit.jupiter.Container;
import org.testcontainers.junit.jupiter.Testcontainers;
import org.testcontainers.mysql.MySQLContainer;

@Testcontainers
class InspectionMigrationIT {
    @Container static final MySQLContainer MYSQL = new MySQLContainer("mysql:8.4");

    @Test void backfills_consistent_history_and_rejects_conflicting_history() throws Exception {
        var flyway = flyway("1");
        flyway.clean();
        flyway.migrate();
        insertResult("result-1", "inspection-1", "artifact://images/a", "a".repeat(64));
        insertResult("result-2", "inspection-1", "artifact://images/a", "a".repeat(64));
        flyway("2").migrate();
        try (var connection = DriverManager.getConnection(MYSQL.getJdbcUrl(), MYSQL.getUsername(), MYSQL.getPassword());
             var statement = connection.createStatement();
             var rows = statement.executeQuery("SELECT status, completed_at FROM inspections")) {
            assertThat(rows.next()).isTrue();
            assertThat(rows.getString("status")).isEqualTo("COMPLETED");
            assertThat(rows.getTimestamp("completed_at")).isNotNull();
            assertThat(rows.next()).isFalse();
        }

        flyway("2").clean();
        flyway("1").migrate();
        insertResult("result-1", "inspection-1", "artifact://images/a", "a".repeat(64));
        insertResult("result-2", "inspection-1", "artifact://images/b", "b".repeat(64));
        assertThatThrownBy(() -> flyway("2").migrate()).rootCause()
                .isInstanceOf(java.sql.SQLIntegrityConstraintViolationException.class)
                .hasMessageContaining("fk_vision_result_inspection");
    }

    private Flyway flyway(String target) {
        return Flyway.configure().dataSource(MYSQL.getJdbcUrl(), MYSQL.getUsername(), MYSQL.getPassword())
                .cleanDisabled(false).target(target).load();
    }

    private void insertResult(String resultId, String inspectionId, String imageUri, String sha256) throws Exception {
        var payload = "{\"input\":{\"image_uri\":\"" + imageUri + "\",\"sha256\":\"" + sha256 + "\"}}";
        try (var connection = DriverManager.getConnection(MYSQL.getJdbcUrl(), MYSQL.getUsername(), MYSQL.getPassword());
             var statement = connection.prepareStatement("INSERT INTO vision_inspection_results VALUES (UNHEX(SHA2(?,256)),?,UNHEX(SHA2(?,256)),?,'fake','0.2','0.6',?,UNHEX(SHA2(?,256)),CURRENT_TIMESTAMP(6))")) {
            statement.setString(1, resultId); statement.setString(2, resultId);
            statement.setString(3, inspectionId); statement.setString(4, inspectionId);
            statement.setString(5, payload); statement.setString(6, payload);
            statement.executeUpdate();
        }
    }
}
