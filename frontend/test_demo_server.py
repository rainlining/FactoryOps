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
        first = demo_server.append_progress_event(
            run["run_id"], "INGEST", "system", "SUCCEEDED", 10, 10, "批次读取完成"
        )
        second = demo_server.append_progress_event(
            run["run_id"], "VISION", "vision", "RUNNING", 1, 10, "正在检测第 1 个产品"
        )

        restored = demo_server.get_run(run["run_id"])

        self.assertEqual([first["sequence"], second["sequence"]], [1, 2])
        self.assertEqual(restored["transport"]["mode"], "http-local")
        self.assertFalse(restored["transport"]["kafka_used"])
        self.assertEqual(restored["progress_events"][-1]["completed_units"], 1)

    def test_worktree_runtime_uses_repository_shared_local_state(self):
        root = Path("C:/repo/.worktrees/feature/frontend")
        self.assertEqual(
            demo_server.resolve_shared_state_dir(root),
            Path("C:/repo/.factoryops-local"),
        )
        self.assertEqual(
            demo_server.resolve_shared_state_dir(Path("C:/repo/frontend")),
            Path("C:/repo/.factoryops-local"),
        )
        self.assertEqual(
            demo_server.resolve_shared_state_dir(
                Path("C:/repo/FactoryOps.worktrees/feature/frontend")
            ),
            Path("C:/repo/FactoryOps/.factoryops-local"),
        )

    def test_queue_artifacts_reject_untrusted_paths_and_digest_mismatch(self):
        with self.assertRaisesRegex(ValueError, "必须包含图片数据"):
            demo_server._store_queue_images(
                [{"name": "x", "artifact": "../.env.local"}]
            )
        with self.assertRaisesRegex(ValueError, "摘要不匹配"):
            demo_server._store_queue_images(
                [{"name": "x", "data": "YQ==", "sha256": "0" * 64}]
            )
        with self.assertRaisesRegex(ValueError, "Artifact 标识无效"):
            demo_server._hydrate_queue_images(
                [{"name": "x", "artifact": "../.env.local"}]
            )

    def test_completed_batch_result_is_restored_with_events(self):
        run = demo_server.create_run("batch-003", 2)
        demo_server.append_progress_event(
            run["run_id"], "COMPLETED", "system", "SUCCEEDED", 2, 2, "批次完成"
        )
        result = {
            "batch_id": "batch-003",
            "item_count": 2,
            "coordinator": "暂停批次",
            "risk": "需要审批",
            "items": [],
        }
        demo_server.complete_run(run["run_id"], result)

        restored = demo_server.get_run(run["run_id"])

        self.assertEqual(restored["status"], "SUCCEEDED")
        self.assertEqual(restored["result"]["coordinator"], "暂停批次")
        self.assertEqual(len(restored["progress_events"]), 1)

    def test_batch_processing_records_real_agent_stages_and_one_batch_conclusion(self):
        run = demo_server.create_run("batch-004", 2)
        images = [
            {"name": "one.png", "data": "aW1hZ2U="},
            {"name": "two.png", "data": "aW1hZ2U="},
        ]
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
        self.assertIn(
            "SPECIALISTS", [event["stage"] for event in restored["progress_events"]]
        )
        self.assertEqual(restored["progress_events"][-1]["stage"], "COMPLETED")

    def test_cancellation_stops_before_batch_conclusion(self):
        run = demo_server.create_run("batch-cancel", 2)
        images = [
            {"name": "one.png", "data": "aW1hZ2U="},
            {"name": "two.png", "data": "aW1hZ2U="},
        ]
        calls = []

        def cancelling_agent(role, instruction, context, image_data=None):
            calls.append(role)
            if role == "vision" and calls.count("vision") == 2:
                demo_server.request_cancel(run["run_id"])
            return "已返回"

        demo_server.process_batch_run(
            run["run_id"], "batch-cancel", images, cancelling_agent
        )
        restored = demo_server.get_run(run["run_id"])

        self.assertEqual(restored["status"], "CANCELLED")
        self.assertNotIn("coordinator", calls)
        self.assertEqual(restored["progress_events"][-1]["status"], "CANCELLED")
        self.assertIsNotNone(restored["result"])
        self.assertEqual(restored["result"]["completed_item_count"], 1)
        self.assertEqual(len(restored["result"]["items"]), 1)

    def test_delete_runs_removes_job_and_progress_events(self):
        run = demo_server.create_run("batch-delete", 1)
        demo_server.append_progress_event(
            run["run_id"], "INGEST", "system", "SUCCEEDED", 1, 1, "已读取"
        )

        deleted = demo_server.delete_runs([run["run_id"]])

        self.assertEqual(deleted, 1)
        self.assertIsNone(demo_server.get_run(run["run_id"]))

    def test_scan_batch_queue_is_idempotent_and_revisions_changed_content(self):
        first = demo_server.scan_batch_queue(
            "factoryops",
            [
                {
                    "batch_id": "batch-001",
                    "display_name": "batch-001",
                    "manifest_digest": "aaa",
                    "images": [{"name": "a.png", "data": "YQ=="}],
                },
                {
                    "batch_id": "batch-002",
                    "display_name": "batch-002",
                    "manifest_digest": "bbb",
                    "images": [{"name": "b.png", "data": "Yg=="}],
                },
            ],
        )
        replay = demo_server.scan_batch_queue(
            "factoryops",
            [
                {
                    "batch_id": "batch-001",
                    "display_name": "batch-001",
                    "manifest_digest": "aaa",
                    "images": [{"name": "a.png", "data": "YQ=="}],
                },
            ],
        )
        changed = demo_server.scan_batch_queue(
            "factoryops",
            [
                {
                    "batch_id": "batch-001",
                    "display_name": "batch-001",
                    "manifest_digest": "ccc",
                    "images": [{"name": "c.png", "data": "Yw=="}],
                },
            ],
        )

        self.assertEqual(first["summary"]["total"], 2)
        self.assertEqual(replay["items"][0]["revision"], 1)
        self.assertEqual(changed["items"][0]["revision"], 2)
        self.assertEqual(len(demo_server.get_batch_queue()["items"]), 3)
        with __import__("sqlite3").connect(demo_server.DB_PATH) as db:
            stored = db.execute(
                "SELECT images FROM batch_queue_items LIMIT 1"
            ).fetchone()[0]
        self.assertNotIn("YQ==", stored)
        self.assertTrue((demo_server.DB_PATH.parent / "queue-images").exists())

    def test_route_batch_outcome_fails_closed_and_routes_approval(self):
        self.assertEqual(
            demo_server.route_batch_outcome(
                {"decision": "PASS", "requires_human_approval": False}
            ),
            "QA_ACCEPTED",
        )
        self.assertEqual(
            demo_server.route_batch_outcome(
                {"decision": "STOP_LINE", "requires_human_approval": True}
            ),
            "WAITING_FOR_APPROVAL",
        )
        self.assertEqual(
            demo_server.route_batch_outcome(
                {"decision": "RECHECK", "requires_human_approval": False}
            ),
            "RECHECK_REQUIRED",
        )
        self.assertEqual(
            demo_server.route_batch_outcome({"decision": "unknown"}), "FAILED"
        )
        self.assertNotEqual(
            demo_server.route_batch_outcome(
                {"coordinator": "批次不合格，发现异常", "risk": "需要进一步判断"}
            ),
            "QA_ACCEPTED",
        )
        self.assertEqual(
            demo_server.route_batch_outcome(
                {"coordinator": "PASS，检验合格", "risk": "无异常"}
            ),
            "FAILED",
        )

    def test_cancel_queued_item_never_creates_a_run(self):
        queue = demo_server.scan_batch_queue(
            "factoryops",
            [
                {
                    "batch_id": "batch-001",
                    "display_name": "batch-001",
                    "manifest_digest": "aaa",
                    "images": [{"name": "a.png", "data": "YQ=="}],
                }
            ],
        )
        item_id = queue["items"][0]["item_id"]

        self.assertTrue(demo_server.cancel_queue_item(item_id))
        restored = demo_server.get_batch_queue()["items"][0]
        self.assertEqual(restored["status"], "CANCELLED")
        self.assertIsNone(restored["run_id"])

    def test_queue_continues_after_an_approval_outcome(self):
        demo_server.scan_batch_queue(
            "factoryops",
            [
                {
                    "batch_id": "batch-risk",
                    "display_name": "batch-risk",
                    "manifest_digest": "risk",
                    "images": [{"name": "a.png", "data": "YQ=="}],
                },
                {
                    "batch_id": "batch-good",
                    "display_name": "batch-good",
                    "manifest_digest": "good",
                    "images": [{"name": "b.png", "data": "Yg=="}],
                },
            ],
        )

        def fake_agent(role, instruction, context, image_data=None):
            if context.get("batch") == "batch-risk" and role in {"coordinator", "risk"}:
                return (
                    '{"decision":"HOLD_BATCH","requires_human_approval":true,"risk_level":"HIGH","policy_refs":["QUALITY-1"]}'
                    if role == "risk"
                    else "建议 HOLD_BATCH"
                )
            if role == "risk":
                return '{"decision":"PASS","requires_human_approval":false,"risk_level":"LOW","policy_refs":[]}'
            return "检验合格，无异常，PASS"

        self.assertTrue(demo_server.start_queue(fake_agent))
        demo_server.QUEUE_WORKER.join(timeout=5)
        items = demo_server.get_batch_queue()["items"]

        self.assertEqual(
            [item["status"] for item in items], ["WAITING_FOR_APPROVAL", "QA_ACCEPTED"]
        )
        self.assertTrue(all(item["run_id"] for item in items))
        good_events = demo_server.get_run(items[1]["run_id"])["progress_events"]
        self.assertEqual(
            [event for event in good_events if event["stage"] == "APPROVAL"][-1][
                "status"
            ],
            "SUCCEEDED",
        )

    def test_recovery_fails_stale_active_item_instead_of_leaving_it_stuck(self):
        queue = demo_server.scan_batch_queue(
            "factoryops",
            [
                {
                    "batch_id": "batch-stale",
                    "display_name": "batch-stale",
                    "manifest_digest": "stale",
                    "images": [{"name": "a.png", "data": "YQ=="}],
                }
            ],
        )
        item_id = queue["items"][0]["item_id"]
        with __import__("sqlite3").connect(demo_server.DB_PATH) as db:
            db.execute(
                "UPDATE batch_queue_items SET status='STARTING' WHERE item_id=?",
                (item_id,),
            )

        self.assertEqual(demo_server.recover_batch_queue(), 1)
        restored = demo_server.get_batch_queue()["items"][0]
        self.assertEqual(restored["status"], "FAILED")
        self.assertIn("重启", restored["error"])

    def test_current_root_does_not_dispatch_batches_from_previous_root(self):
        demo_server.scan_batch_queue(
            "root-a",
            [
                {
                    "batch_id": "a",
                    "display_name": "a",
                    "manifest_digest": "a",
                    "images": [{"name": "a.png", "data": "YQ=="}],
                }
            ],
        )
        current = demo_server.scan_batch_queue(
            "root-b",
            [
                {
                    "batch_id": "b",
                    "display_name": "b",
                    "manifest_digest": "b",
                    "images": [{"name": "b.png", "data": "Yg=="}],
                }
            ],
        )
        self.assertEqual([item["batch_id"] for item in current["items"]], ["b"])
        self.assertEqual(
            [item["batch_id"] for item in demo_server.get_batch_queue()["items"]], ["b"]
        )

    def test_starting_item_can_be_cancelled_before_model_call(self):
        queue = demo_server.scan_batch_queue(
            "factoryops",
            [
                {
                    "batch_id": "a",
                    "display_name": "a",
                    "manifest_digest": "a",
                    "images": [{"name": "a.png", "data": "YQ=="}],
                }
            ],
        )
        item_id = queue["items"][0]["item_id"]
        with __import__("sqlite3").connect(demo_server.DB_PATH) as db:
            db.execute(
                "UPDATE batch_queue_items SET status='STARTING' WHERE item_id=?",
                (item_id,),
            )
        self.assertTrue(demo_server.cancel_queue_item(item_id))
        self.assertEqual(
            demo_server.get_batch_queue()["items"][0]["status"], "CANCELLED"
        )

    def test_recovery_closes_orphan_run_and_can_continue_remaining_queue(self):
        queue = demo_server.scan_batch_queue(
            "factoryops",
            [
                {
                    "batch_id": "lost",
                    "display_name": "lost",
                    "manifest_digest": "lost",
                    "images": [{"name": "a.png", "data": "YQ=="}],
                },
                {
                    "batch_id": "next",
                    "display_name": "next",
                    "manifest_digest": "next",
                    "images": [{"name": "b.png", "data": "Yg=="}],
                },
            ],
        )
        lost = demo_server.create_run("lost", 1)
        with __import__("sqlite3").connect(demo_server.DB_PATH) as db:
            db.execute(
                "UPDATE batch_queue_items SET status='RUNNING',run_id=? WHERE item_id=?",
                (lost["run_id"], queue["items"][0]["item_id"]),
            )
            db.execute("UPDATE batch_queue_control SET status='RUNNING' WHERE id=1")
        self.assertTrue(demo_server.recover_batch_queue())
        self.assertEqual(demo_server.get_run(lost["run_id"])["status"], "FAILED")
        self.assertEqual(demo_server.get_batch_queue()["items"][1]["status"], "QUEUED")


if __name__ == "__main__":
    unittest.main()
