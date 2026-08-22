import unittest
from pathlib import Path

ROOT = Path(__file__).parent


class DashboardContractTest(unittest.TestCase):
    def test_batch_command_center_has_real_progress_and_agent_topology(self):
        html = (ROOT / "dashboard.html").read_text(encoding="utf-8")
        for element_id in (
            "batchProgress",
            "progressLabel",
            "lastActivity",
            "agentTopology",
            "batchConclusion",
            "technicalDetails",
        ):
            self.assertIn(f'id="{element_id}"', html)

    def test_dashboard_uses_async_run_and_event_apis_without_fixed_snapshot(self):
        script = (ROOT / "dashboard.js").read_text(encoding="utf-8")
        self.assertIn('fetch("/api/runs"', script)
        self.assertIn("/events?after=", script)
        self.assertNotIn("demoSnapshot", script)
        self.assertIn("本次本地运行未经过 Kafka", script)

    def test_history_view_does_not_start_a_new_run(self):
        script = (ROOT / "dashboard.js").read_text(encoding="utf-8")
        self.assertIn("showStoredRun(record)", script)
        self.assertNotIn('button.addEventListener("click", runBatch)', script)


if __name__ == "__main__":
    unittest.main()
