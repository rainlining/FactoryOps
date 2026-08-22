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

    def test_product_library_imports_a_root_into_a_batch_queue(self):
        html = (ROOT / "dashboard.html").read_text(encoding="utf-8")
        script = (ROOT / "dashboard.js").read_text(encoding="utf-8")
        for element_id in ("queueSummary", "queueList", "startQueue", "pauseQueue"):
            self.assertIn(f'id="{element_id}"', html)
        self.assertIn("function groupBatchFiles", script)
        self.assertIn('crypto.subtle.digest("SHA-256"', script)
        self.assertIn('fetch("/api/batch-queues/scan"', script)

    def test_queue_actions_report_results_and_terminal_polling_stops(self):
        script = (ROOT / "dashboard.js").read_text(encoding="utf-8")
        self.assertIn("连续检测已启动", script)
        self.assertIn("已创建重试批次", script)
        self.assertIn("已发送取消请求", script)
        self.assertIn("clearInterval(queuePolling)", script)
        self.assertIn("失败原因：", script)


if __name__ == "__main__":
    unittest.main()
