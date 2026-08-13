package com.factoryops.business.inspection.api;

import static org.assertj.core.api.Assertions.assertThat;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.get;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.post;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.jsonPath;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.status;

import com.factoryops.business.inspection.application.InspectionApplicationService;
import com.factoryops.business.inspection.domain.InspectionInput;
import java.util.List;
import java.util.concurrent.CountDownLatch;
import java.util.concurrent.Executors;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.boot.webmvc.test.autoconfigure.AutoConfigureMockMvc;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.test.context.DynamicPropertyRegistry;
import org.springframework.test.context.DynamicPropertySource;
import org.springframework.test.web.servlet.MockMvc;
import org.testcontainers.junit.jupiter.Container;
import org.testcontainers.junit.jupiter.Testcontainers;
import org.testcontainers.mysql.MySQLContainer;

@SpringBootTest(properties="factoryops.clock.fixed=2026-08-13T08:00:00Z")
@AutoConfigureMockMvc
@Testcontainers
class InspectionLifecycleHttpIT {
    @Container static final MySQLContainer MYSQL = new MySQLContainer("mysql:8.4");
    @DynamicPropertySource static void mysql(DynamicPropertyRegistry r) {
        r.add("spring.datasource.url", MYSQL::getJdbcUrl); r.add("spring.datasource.username", MYSQL::getUsername); r.add("spring.datasource.password", MYSQL::getPassword);
    }
    @Autowired MockMvc mvc; @Autowired JdbcTemplate jdbc; @Autowired InspectionApplicationService service;
    @BeforeEach void clean() { jdbc.update("DELETE FROM vision_inspection_results"); jdbc.update("DELETE FROM inspections"); jdbc.update("DELETE FROM batches WHERE kind='PRODUCTION'");jdbc.update("INSERT INTO batches(batch_id_hash,batch_id,kind,product_code,production_line,status,created_at) VALUES(UNHEX(SHA2('B-TEST',256)),'B-TEST','PRODUCTION','P-TEST','LINE-1','OPEN',CURRENT_TIMESTAMP(6))"); }

    @Test void creates_replays_and_queries_pending_inspection() throws Exception {
        var body = request("inspection-1", "artifact://images/a", "a".repeat(64));
        mvc.perform(post("/api/v1/inspections").contentType("application/json").content(body))
                .andExpect(status().isCreated()).andExpect(jsonPath("$.status").value("PENDING")).andExpect(jsonPath("$.replayed").value(false));
        mvc.perform(post("/api/v1/inspections").contentType("application/json").content(body))
                .andExpect(status().isOk()).andExpect(jsonPath("$.replayed").value(true));
        mvc.perform(get("/api/v1/inspections/inspection-1"))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.completed_at").doesNotExist())
                .andExpect(jsonPath("$.result_count").value(0));
    }

    @Test void rejects_identity_conflict_and_reports_missing() throws Exception {
        mvc.perform(post("/api/v1/inspections").contentType("application/json").content(request("inspection-1", "artifact://images/a", "a".repeat(64)))).andExpect(status().isCreated());
        mvc.perform(post("/api/v1/inspections").contentType("application/json").content(request("inspection-1", "artifact://images/b", "b".repeat(64))))
                .andExpect(status().isConflict()).andExpect(jsonPath("$.code").value("inspection_identity_conflict"));
        mvc.perform(get("/api/v1/inspections/missing")).andExpect(status().isNotFound()).andExpect(jsonPath("$.code").value("inspection_not_found"));
        assertThat(jdbc.queryForObject("SELECT COUNT(*) FROM inspections", Integer.class)).isEqualTo(1);
    }

    @Test void rejects_invalid_or_unknown_input() throws Exception {
        mvc.perform(post("/api/v1/inspections").contentType("application/json").content(request("inspection-1", "not-a-uri", "ABC")))
                .andExpect(status().isUnprocessableEntity()).andExpect(jsonPath("$.code").value("invalid_inspection_input"));
        mvc.perform(post("/api/v1/inspections").contentType("application/json").content("{\"inspection_id\":\"i\",\"input\":{\"image_uri\":\"artifact://images/a\",\"sha256\":\""+"a".repeat(64)+"\",\"extra\":1}}"))
                .andExpect(status().isBadRequest());
    }

    @Test void concurrent_identical_creates_choose_one_row_and_replay_the_other() throws Exception {
        var input = new InspectionInput("artifact://images/a", "a".repeat(64));
        var start = new CountDownLatch(1);
        var executor = Executors.newFixedThreadPool(2);
        try {
            var futures = List.of(
                    executor.submit(() -> { start.await(); return service.create("inspection-1", "B-TEST",input); }),
                    executor.submit(() -> { start.await(); return service.create("inspection-1", "B-TEST",input); }));
            start.countDown();
            assertThat(futures).extracting(future -> future.get().replayed())
                    .containsExactlyInAnyOrder(false, true);
        } finally {
            executor.shutdownNow();
        }
        assertThat(jdbc.queryForObject("SELECT COUNT(*) FROM inspections", Integer.class)).isEqualTo(1);
    }

    private String request(String id, String uri, String sha) {
        return "{\"inspection_id\":\""+id+"\",\"batch_id\":\"B-TEST\",\"input\":{\"image_uri\":\""+uri+"\",\"sha256\":\""+sha+"\"}}";
    }
}
