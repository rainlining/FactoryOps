package com.factoryops.business.inspection.api;

import static org.assertj.core.api.Assertions.assertThat;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.post;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.jsonPath;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.status;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.get;

import java.nio.charset.StandardCharsets;
import java.util.List;
import java.util.concurrent.CountDownLatch;
import java.util.concurrent.Executors;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.BeforeEach;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.boot.webmvc.test.autoconfigure.AutoConfigureMockMvc;
import org.springframework.jdbc.core.JdbcTemplate;
import com.factoryops.business.inspection.application.InspectionResultIntake;
import com.factoryops.business.inspection.application.ResultIdentityConflictException;
import tools.jackson.databind.json.JsonMapper;
import org.springframework.test.context.DynamicPropertyRegistry;
import org.springframework.test.context.DynamicPropertySource;
import org.springframework.test.web.servlet.MockMvc;
import org.testcontainers.junit.jupiter.Container;
import org.testcontainers.junit.jupiter.Testcontainers;
import org.testcontainers.mysql.MySQLContainer;

@SpringBootTest
@AutoConfigureMockMvc
@Testcontainers
class InspectionResultHttpIT {
    @Container
    static final MySQLContainer MYSQL = new MySQLContainer("mysql:8.4");

    @DynamicPropertySource
    static void mysql(DynamicPropertyRegistry registry) {
        registry.add("spring.datasource.url", MYSQL::getJdbcUrl);
        registry.add("spring.datasource.username", MYSQL::getUsername);
        registry.add("spring.datasource.password", MYSQL::getPassword);
    }

    @Autowired MockMvc mvc;
    @Autowired JdbcTemplate jdbc;
    @Autowired InspectionResultIntake intake;
    @Autowired JsonMapper mapper;

    @BeforeEach
    void cleanDatabase() {
        jdbc.update("DELETE FROM vision_inspection_results");
        jdbc.update("DELETE FROM inspections");
    }

    @Test
    void creates_then_replays_identical_result_without_extra_row() throws Exception {
        var body = fixture("valid/fake-result.json");
        createInspection(body);
        mvc.perform(post("/api/v1/inspection-results").contentType("application/json").content(body))
                .andExpect(status().isCreated()).andExpect(jsonPath("$.replayed").value(false)).andExpect(jsonPath("$.disposition").value("CREATED"));
        mvc.perform(post("/api/v1/inspection-results").contentType("application/json").content(body))
                .andExpect(status().isOk()).andExpect(jsonPath("$.replayed").value(true)).andExpect(jsonPath("$.disposition").value("REPLAYED"));
        assertThat(jdbc.queryForObject("select count(*) from vision_inspection_results", Integer.class)).isEqualTo(1);
    }

    @Test
    void rejects_invalid_json_and_contract_violation() throws Exception {
        mvc.perform(post("/api/v1/inspection-results").contentType("application/json").content("{"))
                .andExpect(status().isBadRequest());
        mvc.perform(post("/api/v1/inspection-results").contentType("application/json")
                        .content(fixture("invalid/anomaly-score-out-of-range.json")))
                .andExpect(status().isUnprocessableEntity())
                .andExpect(jsonPath("$.code").value("maximum"))
                .andExpect(jsonPath("$.path").value("$.observation.anomaly_score"));
    }

    @Test
    void rejects_same_result_id_with_changed_content() throws Exception {
        var body = fixture("valid/fake-result.json");
        createInspection(body);
        mvc.perform(post("/api/v1/inspection-results").contentType("application/json").content(body))
                .andExpect(status().isCreated());
        var changed = body.replace("\"anomaly_score\": 0.2", "\"anomaly_score\": 0.3");
        mvc.perform(post("/api/v1/inspection-results").contentType("application/json").content(changed))
                .andExpect(status().isConflict()).andExpect(jsonPath("$.code").value("result_identity_conflict"));
    }

    @Test
    void concurrent_identical_requests_create_one_row_and_replay_one() throws Exception {
        var payload = mapper.readTree(fixture("valid/fake-result.json"));
        createInspection(payload.toString());
        var start = new CountDownLatch(1);
        var executor = Executors.newFixedThreadPool(2);
        try {
            var futures = List.of(
                    executor.submit(() -> { start.await(); return intake.accept(payload); }),
                    executor.submit(() -> { start.await(); return intake.accept(payload); }));
            start.countDown();
            assertThat(futures).extracting(future -> future.get().name())
                    .containsExactlyInAnyOrder("CREATED", "REPLAYED");
        } finally {
            executor.shutdownNow();
        }
        assertThat(jdbc.queryForObject("select count(*) from vision_inspection_results", Integer.class)).isEqualTo(1);
    }

    @Test
    void concurrent_conflicting_requests_keep_one_immutable_winner() throws Exception {
        var first = mapper.readTree(fixture("valid/fake-result.json"));
        createInspection(first.toString());
        var second = mapper.readTree(fixture("valid/fake-result.json").replace(
                "\"anomaly_score\": 0.2", "\"anomaly_score\": 0.3"));
        var start = new CountDownLatch(1);
        var executor = Executors.newFixedThreadPool(2);
        try {
            var futures = List.of(
                    executor.submit(() -> outcome(start, first)),
                    executor.submit(() -> outcome(start, second)));
            start.countDown();
            assertThat(futures).extracting(future -> future.get())
                    .containsExactlyInAnyOrder("CREATED", "CONFLICT");
        } finally {
            executor.shutdownNow();
        }
        assertThat(jdbc.queryForObject("select count(*) from vision_inspection_results", Integer.class)).isEqualTo(1);
    }

    private String outcome(CountDownLatch start, tools.jackson.databind.JsonNode payload) throws Exception {
        start.await();
        try {
            return intake.accept(payload).name();
        } catch (ResultIdentityConflictException expected) {
            return "CONFLICT";
        }
    }

    private String fixture(String name) throws Exception {
        try (var input = getClass().getResourceAsStream("/fixtures/" + name)) {
            return new String(input.readAllBytes(), StandardCharsets.UTF_8);
        }
    }

    @Test
    void rejects_valid_result_when_inspection_is_missing_or_input_mismatches() throws Exception {
        var body = fixture("valid/fake-result.json");
        mvc.perform(post("/api/v1/inspection-results").contentType("application/json").content(body))
                .andExpect(status().isUnprocessableEntity()).andExpect(jsonPath("$.code").value("inspection_not_found"));
        var result=mapper.readTree(body); var request=mapper.createObjectNode().put("inspection_id",result.get("inspection_id").asText());
        request.set("input",mapper.createObjectNode().put("image_uri","artifact://images/other").put("sha256",result.get("input").get("sha256").asText()));
        mvc.perform(post("/api/v1/inspections").contentType("application/json").content(request.toString())).andExpect(status().isCreated());
        mvc.perform(post("/api/v1/inspection-results").contentType("application/json").content(body))
                .andExpect(status().isUnprocessableEntity()).andExpect(jsonPath("$.code").value("inspection_input_mismatch"))
                .andExpect(jsonPath("$.path").value("$.input.image_uri"));
        assertThat(jdbc.queryForObject("select count(*) from vision_inspection_results",Integer.class)).isZero();
    }

    @Test
    void first_result_completes_inspection_and_later_result_keeps_completion_time() throws Exception {
        var body=fixture("valid/fake-result.json"); createInspection(body);
        mvc.perform(post("/api/v1/inspection-results").contentType("application/json").content(body)).andExpect(status().isCreated());
        var completed=jdbc.queryForObject("select completed_at from inspections",java.sql.Timestamp.class);
        mvc.perform(get("/api/v1/inspections/inspection-fake-0001"))
                .andExpect(status().isOk()).andExpect(jsonPath("$.result_count").value(1));
        var second=body.replace("result-fake-0001","result-fake-0002");
        mvc.perform(post("/api/v1/inspection-results").contentType("application/json").content(second)).andExpect(status().isCreated());
        assertThat(jdbc.queryForObject("select completed_at from inspections",java.sql.Timestamp.class)).isEqualTo(completed);
        mvc.perform(get("/api/v1/inspections/inspection-fake-0001"))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.status").value("COMPLETED"))
                .andExpect(jsonPath("$.result_count").value(2));
    }

    @Test
    void different_results_concurrently_complete_once_and_both_persist() throws Exception {
        var first=mapper.readTree(fixture("valid/fake-result.json")); createInspection(first.toString());
        var second=first.deepCopy(); ((tools.jackson.databind.node.ObjectNode)second).put("result_id","result-fake-0002");
        var start=new CountDownLatch(1); var executor=Executors.newFixedThreadPool(2);
        try {
            var futures=List.of(executor.submit(()->{start.await();return intake.accept(first);}),executor.submit(()->{start.await();return intake.accept(second);}));
            start.countDown(); assertThat(futures).extracting(f->f.get().name()).containsOnly("CREATED");
        } finally { executor.shutdownNow(); }
        assertThat(jdbc.queryForObject("select count(*) from vision_inspection_results",Integer.class)).isEqualTo(2);
        assertThat(jdbc.queryForObject("select status from inspections",String.class)).isEqualTo("COMPLETED");
        assertThat(jdbc.queryForObject("select completed_at from inspections",java.sql.Timestamp.class)).isNotNull();
    }

    @Test
    void result_insert_failure_rolls_back_inspection_completion() throws Exception {
        var payload = mapper.readTree(fixture("valid/fake-result.json"));
        createInspection(payload.toString());
        jdbc.execute("ALTER TABLE vision_inspection_results ADD CONSTRAINT chk_injected_result_failure CHECK (origin_kind = 'never')");
        try {
            assertThat(org.assertj.core.api.Assertions.catchThrowable(() -> intake.accept(payload))).isNotNull();
        } finally {
            jdbc.execute("ALTER TABLE vision_inspection_results DROP CHECK chk_injected_result_failure");
        }
        assertThat(jdbc.queryForObject("select status from inspections", String.class)).isEqualTo("PENDING");
        assertThat(jdbc.queryForObject("select completed_at from inspections", java.sql.Timestamp.class)).isNull();
        assertThat(jdbc.queryForObject("select count(*) from vision_inspection_results", Integer.class)).isZero();
    }

    private void createInspection(String resultJson) throws Exception {
        var result = mapper.readTree(resultJson);
        var request = mapper.createObjectNode().put("inspection_id", result.get("inspection_id").asText());
        request.set("input", result.get("input"));
        mvc.perform(post("/api/v1/inspections").contentType("application/json").content(request.toString()))
                .andExpect(status().isCreated());
    }
}
