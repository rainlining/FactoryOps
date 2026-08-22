import tempfile
import unittest
from pathlib import Path

import demo_server


class ProgressStoreTest(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        demo_server.DB_PATH = Path(self.temp_dir.name) / "runs.sqlite3"
        demo_server.init_db()

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_progress_events_are_monotonic_and_http_transport_is_explicit(self):
        run = demo_server.create_run("batch-002", 10)
        first = demo_server.append_progress_event(run["run_id"], "INGEST", "system", "SUCCEEDED", 10, 10, "批次读取完成")
        second = demo_server.append_progress_event(run["run_id"], "VISION", "vision", "RUNNING", 1, 10, "正在检测第 1 个产品")

        restored = demo_server.get_run(run["run_id"])

        self.assertEqual([first["sequence"], second["sequence"]], [1, 2])
        self.assertEqual(restored["transport"]["mode"], "http-local")
        self.assertFalse(restored["transport"]["kafka_used"])
        self.assertEqual(restored["progress_events"][-1]["completed_units"], 1)

    def test_completed_batch_result_is_restored_with_events(self):
        run = demo_server.create_run("batch-003", 2)
        demo_server.append_progress_event(run["run_id"], "COMPLETED", "system", "SUCCEEDED", 2, 2, "批次完成")
        result = {"batch_id": "batch-003", "item_count": 2, "coordinator": "暂停批次", "risk": "需要审批", "items": []}
        demo_server.complete_run(run["run_id"], result)

        restored = demo_server.get_run(run["run_id"])

        self.assertEqual(restored["status"], "SUCCEEDED")
        self.assertEqual(restored["result"]["coordinator"], "暂停批次")
        self.assertEqual(len(restored["progress_events"]), 1)

    def test_batch_processing_records_real_agent_stages_and_one_batch_conclusion(self):
        run = demo_server.create_run("batch-004", 2)
        images = [{"name": "one.png", "data": "aW1hZ2U="}, {"name": "two.png", "data": "aW1hZ2U="}]
        calls = []

        def fake_agent(role, instruction, context, image_data=None):
            calls.append((role, context.get("image")))
            return f"{role} 输出"

        demo_server.process_batch_run(run["run_id"], "batch-004", images, fake_agent)
        restored = demo_server.get_run(run["run_id"])

        self.assertEqual(restored["status"], "SUCCEEDED")
        self.assertEqual(restored["result"]["item_count"], 2)
        self.assertEqual(restored["result"]["coordinator"], "coordinator 输出")
        self.assertEqual(restored["result"]["risk"], "risk 输出")
        self.assertEqual([role for role, _ in calls].count("coordinator"), 1)
        self.assertEqual([role for role, _ in calls].count("risk"), 1)
        self.assertIn("SPECIALISTS", [event["stage"] for event in restored["progress_events"]])
        self.assertEqual(restored["progress_events"][-1]["stage"], "COMPLETED")

    def test_cancellation_stops_before_batch_conclusion(self):
        run = demo_server.create_run("batch-cancel", 2)
        images = [{"name": "one.png", "data": "aW1hZ2U="}, {"name": "two.png", "data": "aW1hZ2U="}]
        calls = []

        def cancelling_agent(role, instruction, context, image_data=None):
            calls.append(role)
            demo_server.request_cancel(run["run_id"])
            return "已返回"

        demo_server.process_batch_run(run["run_id"], "batch-cancel", images, cancelling_agent)
        restored = demo_server.get_run(run["run_id"])

        self.assertEqual(restored["status"], "CANCELLED")
        self.assertNotIn("coordinator", calls)
        self.assertEqual(restored["progress_events"][-1]["status"], "CANCELLED")


if __name__ == "__main__":
    unittest.main()
